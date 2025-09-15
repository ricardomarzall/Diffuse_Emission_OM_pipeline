import os
from astropy.io import fits
import numpy as np
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Jupiter_Corrector:
    """Corrige imagens FITS de Jupiter usando modelos específicos para cada filtro.

    Args:
        image_path (str): Caminho da imagem a ser corrigida.
        filtro (str): Nome do filtro utilizado na imagem (ex: "UVW1" ou "UVM2").
        output_path (str, optional): Caminho para salvar a imagem corrigida.
    """
    def __init__(self, image_path, filtro, output_path=None):
        """
        Inicializa o corretor de imagens, carregando os modelos e corrigindo a imagem automaticamente.

        :param image_path: Caminho da imagem a ser corrigida.
        :param filtro: Nome do filtro utilizado na imagem (ex: "UVW1" ou "UVM2").
        :param output_path: (Opcional) Caminho para salvar a imagem corrigida. 
                            Se não for fornecido, um novo nome será gerado automaticamente
                            adicionando '_jpiter_filtred' ao nome do arquivo original.
        """
        self.image_path = image_path
        self.filtro = filtro

        # --- MUDANÇA PRINCIPAL AQUI ---
        if output_path is None:
            # Gera o caminho de saída automaticamente
            base_name, extension = os.path.splitext(self.image_path)
            self.output_path = f"{base_name}_jpiter_filtred{extension}"
        else:
            # Usa o caminho fornecido pelo usuário
            self.output_path = output_path
        
        # Obtém o diretório da biblioteca onde os modelos estão armazenados
        package_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_dir = os.path.join(package_dir, "Modelos_Jupiter")
        self.models = self._load_models()

        # Executa a correção automaticamente ao instanciar a classe
        self.correct_image()

    def _load_models(self):
        """Carrega todos os modelos de correção disponíveis no diretório, organizados por filtro e tamanho.

        Returns:
            dict: Modelos organizados por filtro e tamanho da imagem.
        """
        models = {}
        for file in os.listdir(self.model_dir):
            if file.endswith(".fits"):
                model_path = os.path.join(self.model_dir, file)
                data = fits.getdata(model_path).astype("float")

                # Extrai o nome do filtro do arquivo (supondo que esteja no nome)
                if "UVW1" in file:
                    filtro = "UVW1"
                elif "UVM2" in file:
                    filtro = "UVM2"
                else:
                    continue  # Ignora arquivos sem identificação de filtro

                key = (filtro, data.shape)  # Chave agora inclui o filtro e o tamanho
                models[key] = data
        
        return models

    def _find_best_model(self, image_shape):
        """
        Encontra o modelo que melhor se adapta ao tamanho e filtro da imagem fornecida.

        :return: Modelo correspondente ou None se não encontrar.
        """
        return self.models.get((self.filtro, image_shape), None)

    def correct_image(self):
        """
        Corrige a imagem FITS usando o modelo adequado e salva o resultado,
        PRESERVANDO todas as outras extensões do arquivo original.
        """
        with fits.open(self.image_path) as hdul:
            raw_image = hdul[0].data.astype("float")
    
            model = self._find_best_model(raw_image.shape)
            if model is None:
                raise ValueError(f"Nenhum modelo adequado encontrado para a imagem com filtro {self.filtro}.")
    
            corrected_image = (raw_image / model).astype("float32")
    
            hdul[0].data = corrected_image
    
            hdul[0].header['BITPIX'] = -32
            hdul[0].header['JCORR'] = (True, 'Corrigido com modelo Jupiter')
            hdul[0].header['CDATE'] = (datetime.utcnow().isoformat(), 'Data da correcao')
            hdul[0].header.add_history("Imagem corrigida com o modelo Jupiter.")
    
            hdul.writeto(self.output_path, overwrite=True)
            
        print(f"Imagem corrigida e com todas as extensões preservadas salva em: {self.output_path}")

'''

# EXEMPLO DE USO

Jupiter_Corrector("/net/ASTRO/ricardomarzall/Documentos/lixo_3/0722700101/work/P0722700101OMS413IMAGE_0000.FIT","UVW1")


'''