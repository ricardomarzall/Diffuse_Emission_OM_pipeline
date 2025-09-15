import os
import glob
import re
import subprocess
from astropy.io import fits
from pysas.wrapper import Wrapper as w
import logging

# Configuração de logging padrão, usada apenas se o script for executado de forma independente
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OMAttBatchProcessor:
    """
    Uma classe para encontrar e processar em lote todas as imagens de um
    tipo específico em um diretório de trabalho, executando a tarefa 'omatt'
    do SAS para cada uma.
    """
    
    def __init__(self, work_directory: str, log_func=None, **kwargs):
        """
        Inicializa o processador em lote.

        Args:
            work_directory (str): O diretório de trabalho que contém os arquivos SAS.
            log_func (callable, optional): Função para registrar logs. Se None, usa o módulo logging padrão.
            **kwargs: Argumentos opcionais para a tarefa omatt (ex: tolerance=2.0).
        """
        if not os.path.isdir(work_directory):
            raise FileNotFoundError(f"O diretório de trabalho especificado não existe: {work_directory}")
        
        self.work_directory = work_directory
        self.omatt_kwargs = kwargs
        self.processing_sets = []
        self.log_func = log_func if log_func is not None else logging.info

    def _find_and_pair_files(self):
        """
        Encontra todas as imagens filtradas e as emparelha com seus respectivos
        arquivos de lista de fontes e catálogo.
        """
        self.log_func(f"OMATT: Buscando por imagens '*_jpiter_filtred.FIT' em: {self.work_directory}")
        
        image_pattern = os.path.join(self.work_directory, '*_jpiter_filtred.FIT')
        target_images = glob.glob(image_pattern)

        if not target_images:
            raise FileNotFoundError(f"OMATT ERRO: Nenhuma imagem '*_jpiter_filtred.FIT' encontrada para processar.")

        self.log_func(f"OMATT: Encontradas {len(target_images)} imagens para processar.")

        for image_path in target_images:
            image_filename = os.path.basename(image_path)
            self.log_func(f"--- OMATT: Analisando a imagem: {image_filename} ---")

            try:
                # Usa uma expressão regular mais flexível para capturar todos os formatos de nome de arquivo
                match = re.search(r'P([0-9]{10})(OMS[0-9]{3})', image_filename)
                if not match:
                    self.log_func(f"OMATT Aviso: Não foi possível extrair OBSID e Exposure ID de {image_filename}. Pulando.")
                    continue
                
                obsid, exposure_id = match.groups()

                # Lógica de busca flexível para a lista de fontes
                srl_pattern = os.path.join(self.work_directory, f'P{obsid}{exposure_id}*SWSRLI*.FIT')
                candidate_srl_files = glob.glob(srl_pattern)
                if not candidate_srl_files:
                    self.log_func(f"OMATT Aviso: Nenhuma lista de fontes (*SWSRLI*) encontrada para {exposure_id}. Pulando.")
                    continue
                sourcelist_file = candidate_srl_files[0]

                # Lógica de busca flexível para o catálogo
                cat_pattern = os.path.join(self.work_directory, f'I{obsid}{exposure_id}*USNO*.FIT')
                cat_files = glob.glob(cat_pattern)
                if not cat_files:
                    self.log_func(f"OMATT Aviso: Arquivo de catálogo (*USNO*) não encontrado para {exposure_id}. Pulando.")
                    continue
                catfile_path = cat_files[0]
                
                base, ext = os.path.splitext(image_filename)
                output_filename = f"{base}_rotated_WCS{ext}"
                ppsoswset_file = os.path.join(self.work_directory, output_filename)

                file_set = {
                    'set_file': image_path,
                    'sourcelistset_file': sourcelist_file,
                    'catfile_path': catfile_path,
                    'ppsoswset_file': ppsoswset_file
                }
                self.processing_sets.append(file_set)
                
                self.log_func(f"  + OMATT Par encontrado:")
                self.log_func(f"    - Imagem      : {os.path.basename(file_set['set_file'])}")
                self.log_func(f"    - Source List : {os.path.basename(file_set['sourcelistset_file'])}")
                self.log_func(f"    - Catálogo    : {os.path.basename(file_set['catfile_path'])}")
                self.log_func(f"    - Saída       : {os.path.basename(file_set['ppsoswset_file'])}")

            except Exception as e:
                self.log_func(f"OMATT ERRO inesperado ao processar os arquivos para {image_filename}: {e}")
    
    def run(self):
        self._find_and_pair_files()
        os.environ['SAS_CCF'] = os.path.join(self.work_directory, 'ccf.cif')
        if not self.processing_sets:
            self.log_func("\nOMATT: Nenhum conjunto de arquivos válido foi encontrado para processar.")
            return

        total = len(self.processing_sets)
        self.log_func(f"\n--- OMATT: Iniciando o processamento em lote de {total} conjuntos de arquivos ---")

        for i, file_set in enumerate(self.processing_sets, 1):
            self.log_func(f"\n>>> OMATT: Processando conjunto {i}/{total}: {os.path.basename(file_set['set_file'])}")
            try:
                runner = OMAttRunner(
                    set_file=file_set['set_file'],
                    sourcelistset_file=file_set['sourcelistset_file'],
                    ppsoswset_file=file_set['ppsoswset_file'],
                    catfile_path=file_set['catfile_path'],
                    log_func=self.log_func,
                    **self.omatt_kwargs
                )
                runner.run()
            except Exception as e:
                self.log_func(f"!!!!!! OMATT FALHA AO PROCESSAR O CONJUNTO {i} !!!!!!")
                self.log_func(f"!!!!!! Erro: {e} !!!!!!")
                continue
        
        self.log_func("\n--- OMATT: Processamento em lote concluído. ---")

class OMAttRunner:
    def __init__(self, set_file: str, sourcelistset_file: str, ppsoswset_file: str, catfile_path: str, log_func=None, **kwargs):
        self.set_file = set_file
        self.sourcelistset_file = sourcelistset_file
        self.ppsoswset_file = ppsoswset_file
        self.catfile_path = catfile_path
        self.log_func = log_func if log_func is not None else logging.info
        self.config = {
            'usecat': 'yes' if kwargs.get('usecat', True) else 'no',
            'rotateimage': 'yes' if kwargs.get('rotateimage', True) else 'no',
            'tolerance': kwargs.get('tolerance', 1.5),
            'maxradecerr': kwargs.get('maxradecerr', 1.0),
            'maxrmsres': kwargs.get('maxrmsres', 1.5)
        }
        self.control_flags = {
            'verbosity': kwargs.get('verbosity', 5),
            'warning_level': kwargs.get('warning_level', 1)
        }

    def run(self):
        file_params = {'set': self.set_file, 'sourcelistset': self.sourcelistset_file, 'ppsoswset': self.ppsoswset_file, 'catfile': self.catfile_path}
        full_params_dict = {**file_params, **self.config}
        params_list = [f'{key}={value}' for key, value in full_params_dict.items()]
        control_flags_list = ['-w', str(self.control_flags['warning_level']), '-V', str(self.control_flags['verbosity'])]
        final_params = params_list + control_flags_list
        full_command_str = f"omatt {' '.join(final_params)}"
        self.log_func(f"OMATT: Executando o comando:\n{full_command_str}\n")
        try:
            w('omatt', final_params).run()
            self.log_func("\n--- OMATT: Tarefa omatt concluída com sucesso! ---")
        except subprocess.CalledProcessError as e:
            self.log_func(f"\n--- OMATT ERRO: A execução de omatt falhou com o código de saída {e.returncode} ---")
            raise e