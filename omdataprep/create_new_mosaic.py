import os
import re
import glob
from pysas.wrapper import Wrapper as w
from astropy.io import fits
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Build_Mosaic:
    """
    Constrói mosaicos ou empilha imagens XMM-Newton OM.
    Detecta automaticamente o modo (Mosaico Híbrido ou FSIMAG) e aplica a lógica correta.
    """
    def __init__(self, directory):
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"O diretório especificado não existe: {directory}")
        self.directory = os.path.abspath(directory)
        logging.info(f"Diretório de trabalho definido como: {self.directory}")

    def init_sas_environment(self):
        if not os.getenv('SAS_DIR'):
            logging.warning("AVISO: Ambiente SAS não parece estar inicializado.")

    def get_obsid(self, filenames):
        if not filenames: return "UNKNOWN_OBSID"
        basename = os.path.basename(filenames[0])
        match = re.match(r'(P\d+)', basename)
        if match: return match.group(1)
        return "UNKNOWN_OBSID"
    
    def get_exposure_id(self, filename):
        basename = os.path.basename(filename)
        match = re.search(r'(OMS\d+)', basename)
        if match: return match.group(1)
        return None

    def get_filter_from_header(self, filepath):
        try:
            with fits.open(filepath) as hdul:
                for hdu in hdul:
                    if 'FILTER' in hdu.header:
                        return hdu.header['FILTER'].strip().upper()
            return 'UNKNOWN'
        except Exception as e:
            logging.error(f"ERRO ao ler o arquivo FITS {os.path.basename(filepath)}: {e}")
            return "UNKNOWN"

    def find_images_for_hybrid_mosaic(self, filter_name='UVW1'):
        all_files_basenames = os.listdir(self.directory)
        final_image_list = []
        
        jupiter_corrected_files = [
            f for f in all_files_basenames 
            if "jpiter_filtred" in f and "rotated_WCS" in f and "IMAGE_1000" in f
        ]
        
        if not jupiter_corrected_files:
            # Esta mensagem é normal se não houver dados para um filtro específico
            logging.debug(f"Nenhum arquivo de mosaico corrigido ('jpiter_filtred' e 'IMAGE_1000') encontrado para o filtro {filter_name}.")
            return []

        jupiter_corrected_files.sort()

        jupiter_corrected_file = None
        for f_basename in jupiter_corrected_files:
            full_path = os.path.join(self.directory, f_basename)
            if self.get_filter_from_header(full_path) == filter_name:
                jupiter_corrected_file = f_basename
                break
        
        if not jupiter_corrected_file:
            logging.debug(f"Nenhum arquivo de mosaico foi validado para o filtro {filter_name}.")
            return []

        final_image_list.append(jupiter_corrected_file)
        corrected_exposure_id = self.get_exposure_id(jupiter_corrected_file)
        logging.info(f"Arquivo principal para Mosaico ({filter_name}) encontrado: {jupiter_corrected_file}")

        simage_candidates = [f for f in all_files_basenames if 'SIMAGE1000' in f]
        
        for simage_basename in simage_candidates:
            simage_exposure_id = self.get_exposure_id(simage_basename)
            if simage_exposure_id != corrected_exposure_id:
                full_path_simage = os.path.join(self.directory, simage_basename)
                if self.get_filter_from_header(full_path_simage) == filter_name:
                    final_image_list.append(simage_basename)
        
        return sorted(list(set(final_image_list)))

    def create_new_mosaic(self):
        self.init_sas_environment()
        
        # --- DETECÇÃO DE MODO ---
        # =====================================================================================
        #  LÓGICA FSIMAG AJUSTADA: Procura apenas por arquivos FIMAG que foram corrigidos
        # =====================================================================================
        fsimag_files = glob.glob(os.path.join(self.directory, 'P*FIMAG*jpiter_filtred_rotated_WCS.FIT'))
        
        if fsimag_files:
            # --- MODO FSIMAG ---
            logging.info(f"--- Modo FSIMAG detectado: {len(fsimag_files)} arquivos corrigidos encontrados ---")
            
            images_by_filter = {}
            for f_path in fsimag_files:
                filter_name = self.get_filter_from_header(f_path)
                if filter_name != 'UNKNOWN':
                    images_by_filter.setdefault(filter_name, []).append(os.path.basename(f_path))

            if not images_by_filter:
                logging.error("Arquivos FSIMAG corrigidos encontrados, mas não foi possível agrupar por filtro.")
                return

            logging.info(f"Imagens FSIMAG agrupadas por filtro: { {k: len(v) for k, v in images_by_filter.items()} }")
            
            original_dir = os.getcwd()
            try:
                os.chdir(self.directory)
                for filter_name, image_list in images_by_filter.items():
                    if len(image_list) < 1:
                        continue
                    
                    logging.info(f"\nProcessando filtro FSIMAG: {filter_name}")
                    obsid = self.get_obsid(image_list)
                    imagesets_str = ' '.join(image_list)
                    output_name = f"{obsid}_{filter_name}_jupiter_filtred_MOSAIC.FIT"
                    
                    logging.info(f"Empilhando {len(image_list)} imagens para o arquivo: {output_name}")
                    
                    params = [f'imagesets={imagesets_str}', f'mosaicedset={output_name}']
                    w('ommosaic', params).run()
                    logging.info(f"SUCESSO! Imagem empilhada '{output_name}' criada.")
            except Exception as e:
                logging.critical(f"ERRO CRÍTICO ao executar ommosaic no modo FSIMAG: {e}")
            finally:
                os.chdir(original_dir)

        else:
            # --- MODO MOSAICO HÍBRIDO ---
            logging.info("--- Nenhum arquivo FSIMAG corrigido encontrado. Procedendo com o Modo Mosaico Híbrido ---")
            
            processed_filters = []
            for target_filter in ['UVW1', 'UVM2', 'UVL', 'U', 'B', 'V', 'WHITE']:
                logging.info(f"\nProcurando imagens de mosaico para o filtro {target_filter}...")
                image_files = self.find_images_for_hybrid_mosaic(filter_name=target_filter)
                
                if not image_files:
                    logging.info(f"Nenhuma imagem válida foi encontrada para o mosaico {target_filter}.")
                    continue
                
                processed_filters.append(target_filter)
                logging.info(f"Arquivos selecionados para o mosaico ({target_filter}): {image_files}")
                obsid = self.get_obsid(image_files)
                imagesets_str = ' '.join(image_files)
                output_name = f"{obsid}_{target_filter}_jupiter_filtred_MOSAIC.FIT"
                
                logging.info(f"Criando mosaico: {output_name}")
                
                original_dir = os.getcwd()
                try:
                    os.chdir(self.directory)
                    params = [
                        f'imagesets={imagesets_str}', f'mosaicedset={output_name}',
                        'correlset=', 'nsigma=2', 'mincorr=0', 'minfraction=0.5',
                        'maxdx=5', 'binaxis=0', 'numintervals=2', 'di=10', 'minnumpixels=100',
                        '-w', '1', '-V', '4'
                    ]
                    w('ommosaic', params).run()
                    logging.info(f"SUCESSO! Mosaico '{output_name}' criado. 🎉")
                except Exception as e:
                    logging.critical(f"ERRO CRÍTICO ao executar ommosaic no modo Mosaico: {e}")
                finally:
                    os.chdir(original_dir)
            
            if not processed_filters:
                logging.warning("Nenhum arquivo processável foi encontrado no diretório para nenhum filtro.")


# --- COMO EXECUTAR O SCRIPT ---
#if __name__ == '__main__':
#    # Altere este caminho para o diretório de dados que você quer processar
#    caminho_para_dados = '/net/ASTRO/ricardomarzall/Documentos/WD/OM/teste_FSIMAG/0500760101/work'
#    
#    mosaic_builder = Build_Mosaic(caminho_para_dados)
#    mosaic_builder.create_new_mosaic()