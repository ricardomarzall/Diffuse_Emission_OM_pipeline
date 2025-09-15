import os
import numpy as np
from astropy.io import fits
from glob import glob
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UVImageCombiner:
    """Combina imagens FITS UVW1 e UVM2, somando os dados e salvando o resultado.

    Args:
        directory (str): Diretório onde estão as imagens a serem combinadas.
    """
    def __init__(self, directory):
        self.directory = directory

    def get_matching_pairs(self):
        """Encontra pares de arquivos UVM2 e UVW1 com o mesmo prefixo P*."""
        # O glob para o primeiro arquivo está ok para o seu diretório
        uvm2_files = glob(os.path.join(self.directory, 'P*_UVW1_jupiter_filtred_MOSAIC.FIT')) 
        # O glob para o segundo arquivo está ok
        uvw1_files = glob(os.path.join(self.directory, 'P*RSIMAGM*.FIT'))

        pairs = []
        
        # A lógica para extrair a chave do primeiro arquivo está correta
        uvm2_dict = {os.path.basename(f).split('_')[0]: f for f in uvm2_files}
        
        # A lógica para extrair a chave do segundo arquivo PRECISA SER CORRIGIDA ASSIM:
        uvw1_dict = {os.path.basename(f).split('OMS')[0]: f for f in uvw1_files} # <<<<<<< LINHA CORRIGIDA

        # Pega apenas os prefixos que têm os dois filtros
        common_keys = set(uvm2_dict.keys()).intersection(uvw1_dict.keys())

        for key in sorted(common_keys):
            pairs.append((uvm2_dict[key], uvw1_dict[key]))

        return pairs

    def combine_two_images(self, file1, file2):
        """Soma duas imagens FITS ignorando NaNs."""
        with fits.open(file1) as hdul1, fits.open(file2) as hdul2:
            data1 = np.nan_to_num(hdul1[0].data.astype(np.float32))
            data2 = np.nan_to_num(hdul2[0].data.astype(np.float32))
            combined_data = data1 + data2
            header = hdul1[0].header  # Usa o header do primeiro arquivo
        return combined_data, header

    def save_combined_image(self, data, header, output_filename):
        """Salva a imagem FITS combinada."""
        output_path = os.path.join(self.directory, output_filename)
        fits.writeto(output_path, data, header, overwrite=True)
        logging.info(f"✅ Arquivo salvo: {output_path}")

    def run(self):
        """Executa o processo de combinação para todos os pares."""
        pairs = self.get_matching_pairs()
        if not pairs:
            logging.error("❌ Nenhum par de arquivos correspondente foi encontrado.")
            return

        for file1, file2 in pairs:
            prefix = os.path.basename(file1).split('_')[0]
            combined_data, header = self.combine_two_images(file1, file2)
            output_filename = f"{prefix}_combined_UVM2_UVW1.fits"
            self.save_combined_image(combined_data, header, output_filename)


# ==== Exemplo de uso ====
#UVImageCombiner("/net/ASTRO/ricardomarzall/Documentos/WD/OM/BASE_PARA_TESTES_CODIGO/0722700101/work").run()

