import os
import shutil
import subprocess
import tarfile
import glob  # Usaremos glob para simplificar a busca de arquivos
from pysas.wrapper import Wrapper as w
from .jupiter_corrector import Jupiter_Corrector
from .create_new_mosaic import *
from astropy.io import fits
import re
from .mosaic_combiner import *
from .omatt import *
import logging
from .SExtractor import running_Sextractor, apply_segmentation_mask
from .check_fits import sincronizar_wcs_de_fits

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RunOmichain:
    """Executa o processamento completo do pipeline OM, incluindo extração, correção, mosaico e remoção de fontes pontuais.

    Args:
        directory (str): Diretório base dos dados.
        initsas_path (str): Caminho para o script de inicialização SAS.
        remove_odf (bool): Remove diretórios ODF após processamento.
        remove_tar (bool): Remove arquivos .tar.gz após extração.
    """
    def __init__(self, directory, initsas_path, remove_odf=False, remove_tar=False):
        self.directory = directory
        self.initsas_path = initsas_path
        self.remove_odf = remove_odf
        self.remove_tar = remove_tar
        self.log_file_path = os.path.join(directory, "process_omichain_log.txt")
        self.processed_observations = []
        self.error_observations = []
        self.already_processed = []
        self.run()

    def log_message(self, message):
        """Registra mensagem no log e no console."""
        with open(self.log_file_path, 'a') as log_file:
            log_file.write(message + '\n')
        logging.info(message)

    def unpack_tar_files(self, directory):
        for file_name in os.listdir(directory):
            if file_name.endswith((".tar.gz", ".TAR")):
                tar_path = os.path.join(directory, file_name)
                self.log_message(f"Desempacotando {tar_path}")
                with tarfile.open(tar_path, 'r:*') as tar:
                    tar.extractall(directory)

    def update_initsas_script(self, script_path, odf_dir):
        with open(script_path, 'r') as file:
            lines = file.readlines()
        with open(script_path, 'w') as file:
            for line in lines:
                if "SAS_ODF=" in line:
                    file.write(f"SAS_ODF={odf_dir}; export SAS_ODF\n")
                else:
                    file.write(line)
                    
    def remove_tar_file(self, directory, folder_name):
        tar_file_path = os.path.join(directory, f"{folder_name}.tar.gz")
        if os.path.exists(tar_file_path):
            try:
                os.remove(tar_file_path)
                self.log_message(f"Arquivo {tar_file_path} excluído com sucesso.")
            except Exception as e:
                self.log_message(f"Erro ao excluir {tar_file_path}: {e}")
        else:
            self.log_message(f"Nenhum arquivo .tar.gz encontrado para {folder_name}.")                

    def run_commands_in_directory(self, directory, sas_file):
        self.log_message(f"Entrando no diretório: {directory}")
        os.environ['SAS_ODF'] = os.path.join(directory, sas_file)
        os.environ['SAS_CCF'] = os.path.join(directory, 'ccf.cif')

        self.log_message(f"SAS_ODF: {os.environ['SAS_ODF']}")
        self.log_message(f"SAS_CCF: {os.environ['SAS_CCF']}")

        if not os.path.exists(os.environ['SAS_ODF']):
            raise FileNotFoundError(f"Arquivo .SAS {os.environ['SAS_ODF']} não encontrado.")

        current_dir = os.getcwd()
        os.chdir(directory)
        try:
            self.log_message("Executando sasver...")
            w('sasver', []).run()
            self.log_message("Executando omichain...")
            w('omichain', ['filters="UVW1 UVM2"']).run()
            self.log_message(f"Comando omichain executado em {directory}")
            return True
        except Exception as e:
            self.log_message(f"Erro ao executar sasver ou omichain: {e}")
            return False
        finally:
            os.chdir(current_dir)

    def remove_odf_directory(self, directory):
        odf_dir = os.path.join(directory, "odf")
        if self.remove_odf and os.path.exists(odf_dir):
            try:
                shutil.rmtree(odf_dir)
                self.log_message(f"Pasta 'odf' excluída com sucesso: {odf_dir}")
            except Exception as e:
                self.log_message(f"Erro ao excluir a pasta 'odf': {e}")
        elif not self.remove_odf:
            self.log_message("Configuração definida para não excluir a pasta 'odf'.")

    def run(self):
        for folder_name in os.listdir(self.directory):
            folder_path = os.path.join(self.directory, folder_name)
            if os.path.isdir(folder_path):
                self.log_message(f"Processando observação: {folder_name}")
                work_dir = os.path.join(folder_path, "work")
                if os.path.exists(work_dir):
                    self.log_message(f"A pasta 'work' já existe em {folder_name}, assumindo que o omichain já foi executado.")
                    self.already_processed.append(folder_name)
                    continue

                odf_dir = os.path.join(folder_path, "odf") if os.path.exists(os.path.join(folder_path, "odf")) else folder_path
                self.log_message(f"Usando {odf_dir} como diretório de entrada.")
                self.log_message(f"Criando pasta 'work' em {folder_name}.")
                os.makedirs(work_dir, exist_ok=True)

                try:
                    initsas_dest_path = os.path.join(work_dir, "initsas.sh")
                    shutil.copy(self.initsas_path, initsas_dest_path)
                    self.log_message(f"Arquivo initsas.sh copiado para {work_dir}")

                    self.unpack_tar_files(odf_dir)
                    self.update_initsas_script(initsas_dest_path, odf_dir)
                    self.log_message(f"Script initsas.sh atualizado para usar o diretório {odf_dir}")

                    subprocess.run(["bash", "-c", f"cd {work_dir} && . ./initsas.sh"], check=True)
                    self.log_message(f"Script initsas.sh executado em {work_dir}")

                    sas_files = [f for f in os.listdir(work_dir) if f.endswith('.SAS')]
                    if sas_files:
                        sas_file = sas_files[0]
                        if self.run_commands_in_directory(work_dir, sas_file):
                            self.processed_observations.append(folder_name)

                            patterns_to_find = [
                                'P*FIMAG_0000.FIT', # Padrão para FSIMAG
                                'P*IMAGE_0000.FIT', # Padrão para Mosaico (às vezes ocorre)
                                'P*IMAGE_1000.FIT'  # Padrão para Mosaico (componentes)
                            ]


                            files_to_correct = []
                            for pattern in patterns_to_find:
                                files_to_correct.extend(glob.glob(os.path.join(work_dir, pattern)))
                            
                            # Remove duplicados se houver e ordena para consistência
                            files_to_correct = sorted(list(set(files_to_correct)))

                            if not files_to_correct:
                                self.log_message("Nenhum arquivo para correção de Júpiter foi encontrado (*FIMAG* ou *IMAGE*).")

                            for file_path in files_to_correct:
                                file_name = os.path.basename(file_path)
                                try:
                                    # Determina o modo (FSIMAG ou Mosaico) para o log
                                    mode = "FSIMAG" if "FIMAG" in file_name else "Mosaico"

                                    with fits.open(file_path) as hdul:
                                        header = hdul[0].header
                                        if header.get("FILTER", "") == "UVW1":
                                            self.log_message(f"Imagem de {mode} '{file_name}' com filtro UVW1 encontrada.")
                                            Jupiter_Corrector(file_path,"UVW1")
                                            self.log_message(f"Correção aplicada à imagem {file_name}")
                                        
                                except Exception as e:
                                    self.log_message(f"Erro ao verificar ou corrigir {file_name}: {e}")

                            
                        else:
                            self.error_observations.append(folder_name)                         
                   
                        try:
                            print(f"Iniciando o processador em lote para o diretório: {work_dir}")
                            batch_processor = OMAttBatchProcessor(
                                work_directory=f'{folder_path}/work',
                                tolerance=2.0,
                                verbosity=4,
                                log_func=self.log_message  # Adicione esta linha
                            )
                            batch_processor.run()
                            self.log_message(f" OMATT rodado para imagens filtradas com Júpiter")

                        except (FileNotFoundError, ValueError) as e:
                            self.log_message(f"OMATT \nERRO na configuração ou busca de arquivos: {e}")
                        except Exception as e:
                            self.log_message(f"OMATT \nOcorreu um erro inesperado durante a execução: {e}")                       
                        try:
                            sincronizar_wcs_de_fits(work_dir)
                            self.log_message(f"Mudança nos cabeçalho da imagem")
                        except Exception as e:
                            self.log_message("Erro insperado em mudar o cabeçalho")
                        
                        try:
                            mosaic_builder = Build_Mosaic(f'{folder_path}/work')
                            mosaic_builder.create_new_mosaic()
                            self.log_message("BUILD MOSAIC: MOSAICO UVW1 Jupiter Filtred Criado com Sucesso! ")
                        except FileNotFoundError as e:
                            self.log_message(f"BUILD MOSAIC: Um arquivo ou diretório necessário não foi encontrado: {e}")
                        except Exception as e:
                            self.log_message(f"BUILD MOSAIC: Ocorreu um erro inesperado: {e}")
                            
                        try:
                            UVImageCombiner(f'{folder_path}/work').run()
                            self.log_message(f'Mosaicos UVW1 e UVM2 combinadas com sucesso')
                        except Exception as e:
                            self.log_message(f"Erro ao combinar os Mosaicos UVW1 e UVM2: {e}")
                                
                        try:
                            self.log_message("Iniciando geração de mapas de segmentação com SExtractor...")
                            running_Sextractor(work_dir, log_func=self.log_message)
                            self.log_message("Geração de mapas de segmentação concluída.")
                        except Exception as e:
                            self.log_message(f"Erro ao rodar SExtractor: {e}")

                        try:
                            self.log_message("Iniciando aplicação de máscara de segmentação...")
                            apply_segmentation_mask(work_dir, log_func=self.log_message)
                            self.log_message("Aplicação de máscara de segmentação concluída.")
                        except Exception as e:
                            self.log_message(f"Erro ao aplicar a máscara de segmentação: {e}")

                    else:
                        self.log_message(f"Nenhum arquivo .SAS encontrado em {work_dir}")
                        self.error_observations.append(folder_name)

                    self.remove_odf_directory(folder_path)
                        
                except Exception as e:
                    self.log_message(f"Erro ao processar a observação {folder_name}: {e}")
                    self.error_observations.append(folder_name)

                if self.remove_tar:
                    self.remove_tar_file(self.directory, folder_name)