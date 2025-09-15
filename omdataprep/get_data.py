import pandas as pd
import os
import subprocess
import tarfile
import shutil
from datetime import datetime
import logging

# Configuração básica do logging (se já não estiver no seu script principal)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

class Download:
    """Classe responsável pelo download de arquivos ODF a partir de um CSV.

    Args:
        csv_file_path (str): Caminho para o arquivo CSV com os OBSIDs.
        destination_directory (str): Diretório onde os arquivos serão salvos.
        aioclient_path (str): Caminho para o cliente de download.
        start (int): Índice inicial do CSV.
        end (int): Índice final do CSV.
        instname (str): Nome do instrumento.
        filter_name (str): Filtros a serem usados no download.
    """
    def __init__(self, csv_file_path, destination_directory, aioclient_path, start, end, instname, filter_name):
        self.csv_file_path = csv_file_path
        self.destination_directory = destination_directory
        self.aioclient_path = aioclient_path
        self.lib_directory = os.path.join(aioclient_path, 'lib')
        self.start = start
        self.end = end 
        self.df = None
        self.instname = instname
        self.filter_name = filter_name
        
        # Garante que o diretório de destino exista
        os.makedirs(self.destination_directory, exist_ok=True)
        
        # Define o nome do log
        log_base = os.path.join(self.destination_directory, "log_download.txt")
        if os.path.exists(log_base):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = os.path.join(self.destination_directory, f"log_download_{timestamp}.txt")
        else:
            self.log_file = log_base
    
    def escrever_log(self, mensagem):
        """Registra uma mensagem no arquivo de log."""
        try:
            with open(self.log_file, "a") as log:
                log.write(mensagem + "\n")
        except Exception as e:
            logging.error(f"Erro ao escrever no log: {e}")

    def carregar_csv(self):
        """Carrega o arquivo CSV com os OBSIDs."""
        self.df = pd.read_csv(self.csv_file_path, delimiter=",", comment="#")
        if 'OBSERVATION.OBSERVATION_ID' not in self.df.columns:
            raise ValueError("A coluna 'OBSERVATION.OBSERVATION_ID' não foi encontrada no arquivo CSV.")

    def baixar_observacoes(self):
        """Realiza o download dos arquivos ODF para os OBSIDs especificados."""
        df_subset = self.df.iloc[self.start:self.end]
        
        # =======================================================================
        # INÍCIO DO BLOCO DE CÓDIGO MODIFICADO
        # =======================================================================

        # Cria um conjunto com os nomes base dos arquivos .tar.gz existentes
        tars_existentes = {f.split(".")[0] for f in os.listdir(self.destination_directory) if f.endswith(".tar.gz")}
        
        # Cria um conjunto com os nomes das pastas existentes no diretório
        pastas_existentes = {d for d in os.listdir(self.destination_directory) if os.path.isdir(os.path.join(self.destination_directory, d))}
        
        # Une os dois conjuntos para ter uma lista completa de OBSIDs a pular
        obsids_a_pular = tars_existentes.union(pastas_existentes)

        # =======================================================================
        # FIM DO BLOCO DE CÓDIGO MODIFICADO
        # =======================================================================

        for obsid in df_subset['OBSERVATION.OBSERVATION_ID']:
            obsid_str = str(obsid).zfill(10)

            if obsid_str in obsids_a_pular:
                mensagem = f"OBSID {obsid_str} já existe (pasta ou .tar.gz). Pulando..."
                logging.info(mensagem)
                self.escrever_log(mensagem)
                continue

            command = f'./aioclient -L "GET obsno={obsid_str} instname={self.instname} filter={self.filter_name} level=ODF" -O {self.destination_directory}'
            try:
                result = subprocess.run(command, shell=True, check=True, cwd=self.aioclient_path, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                mensagem = f"Download concluído para obsid {obsid_str}"
                logging.info(mensagem)
                self.escrever_log(mensagem)
            except subprocess.CalledProcessError as e:
                erro_msg = f"Erro ao baixar obsid {obsid_str}: {e.stderr.decode('utf-8', errors='ignore')}"
                logging.error(erro_msg)
                self.escrever_log(erro_msg)
        logging.info("Download concluído para todos os OBSID.")

class Extract:
    """Classe responsável por extrair e organizar arquivos .tar.gz baixados.

    Args:
        directory (str): Diretório onde estão os arquivos .tar.gz.
        remove_tar (bool): Se True, remove os arquivos .tar.gz após extração.
    """
    def __init__(self, directory, remove_tar=False):
        self.directory = directory
        self.remove_tar = remove_tar
        self.log_file = os.path.join(directory, "extract_log.txt")

    def log_message(self, message):
        """Registra mensagens no log e no console."""
        with open(self.log_file, "a") as log:
            log.write(message + "\n")
        logging.info(message)

    def remove_tar_file(self, tar_path):
        """Remove o arquivo .tar.gz se existir."""
        if os.path.exists(tar_path):
            try:
                os.remove(tar_path)
                self.log_message(f"Arquivo {tar_path} excluído com sucesso.")
            except Exception as e:
                self.log_message(f"Erro ao excluir {tar_path}: {e}")

    def extract_and_organize(self):
        """Extrai e organiza os arquivos .tar.gz no diretório especificado."""
        if not os.path.exists(self.directory):
            logging.error(f"O diretório {self.directory} não existe.")
            return
        for filename in os.listdir(self.directory):
            if filename.endswith(".tar.gz"):
                try:
                    number = filename.split('.')[0]
                    extract_dir = os.path.join(self.directory, number)
                    if os.path.exists(extract_dir):
                        self.log_message(f"{filename} já foi extraído para {extract_dir}. Pulando.")
                        continue
                    os.makedirs(extract_dir, exist_ok=True)
                    tar_path = os.path.join(self.directory, filename)
                    # Extraindo os arquivos
                    with tarfile.open(tar_path, "r:gz") as tar:
                        tar.extractall(path=extract_dir)
                    self.log_message(f"Arquivo {filename} extraído para {extract_dir}")
                    # Criando a pasta "odf" e movendo os arquivos para lá
                    odf_dir = os.path.join(extract_dir, "odf")
                    os.makedirs(odf_dir, exist_ok=True)
                    for item in os.listdir(extract_dir):
                        item_path = os.path.join(extract_dir, item)
                        if os.path.isfile(item_path):
                            shutil.move(item_path, os.path.join(odf_dir, item))
                    self.log_message(f"Arquivos movidos para a pasta {odf_dir}")
                    # Removendo o arquivo .tar.gz se a opção estiver ativada
                    if self.remove_tar:
                        self.remove_tar_file(tar_path)
                except Exception as e:
                    self.log_message(f"Erro ao processar {filename}: {e}")
