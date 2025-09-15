import os
import glob
import subprocess
import argparse
from astropy.io import fits
import numpy as np

def running_Sextractor(diretorio_alvo, log_func=None):
    """
    Processa um diretório para gerar mapas de segmentação usando SExtractor.
    """
    if log_func is None:
        def log_func(msg):
            print(msg)

    log_func(f"\n--- Iniciando processamento com SExtractor no diretório: {diretorio_alvo} ---")

    if not os.path.isdir(diretorio_alvo):
        log_func(f"ERRO: O diretório '{diretorio_alvo}' não existe.")
        return

    config_file = "/net/ASTRO/ricardomarzall/Documentos/Diffuse_Emission_UV/Data_reduction/omdataprep/config_sextractor/default.sex"

    if not os.path.isfile(config_file):
        log_func(f"ERRO: Arquivo de configuração não encontrado em '{config_file}'")
        return

    padroes = [
        "*_combined_UVM2_UVW1.fits",
        "*_UVW1_jupiter_filtred_MOSAIC.FIT",
        "P*RSIMAGM*.FIT"
    ]

    arquivos_encontrados = 0
    for padrao in padroes:
        caminho_busca = os.path.join(diretorio_alvo, padrao)
        for arquivo_entrada in glob.glob(caminho_busca):
            if '_segmentation_map' in arquivo_entrada or '_masked' in arquivo_entrada:
                continue
            
            arquivos_encontrados += 1
            
            base, ext = os.path.splitext(os.path.basename(arquivo_entrada))
            arquivo_saida = f"{base}_segmentation_map{ext}"
            caminho_saida_completo = os.path.join(diretorio_alvo, arquivo_saida)
            
            log_func(f"\n[Processando]: {os.path.basename(arquivo_entrada)}")
            log_func(f"  -> Saída será: {arquivo_saida}")
            
            command = [
                'source-extractor',
                arquivo_entrada,
                '-c', config_file,
                '-CHECKIMAGE_NAME', caminho_saida_completo
            ]
            
            try:
                result = subprocess.run(command, check=True, text=True, capture_output=True)
                log_func(f"  -> SUCESSO! Arquivo de segmentação salvo.")
                if result.stdout:
                    log_func(result.stdout)
                if result.stderr:
                    log_func(result.stderr)
            except subprocess.CalledProcessError as e:
                log_func(f"  -> ERRO ao processar o arquivo com SExtractor.")
                log_func(f"     Saída de erro do SExtractor:\n{e.stderr}")
    
    if arquivos_encontrados == 0:
        log_func("Nenhum arquivo novo correspondente aos padrões foi encontrado para o SExtractor.")
        
    log_func("\n--- Processamento com SExtractor concluído. ---")


def apply_segmentation_mask(diretorio_alvo, log_func=None):
    """
    Aplica máscaras de segmentação de forma robusta, lidando com diferentes estruturas de FITS.
    """
    if log_func is None:
        def log_func(msg):
            print(msg)
            
    log_func(f"\n--- Iniciando aplicação de máscara de segmentação em: {diretorio_alvo} ---")

    if not os.path.isdir(diretorio_alvo):
        log_func(f"ERRO: O diretório '{diretorio_alvo}' não existe.")
        return

    caminho_busca_seg = os.path.join(diretorio_alvo, "*_segmentation_map.*")
    mapas_de_segmentacao = glob.glob(caminho_busca_seg)
     
    arquivos_processados = 0
    for seg_map_path in mapas_de_segmentacao:
        dir_name = os.path.dirname(seg_map_path)
        base_seg_name = os.path.basename(seg_map_path)
        original_base_name = base_seg_name.replace('_segmentation_map', '')
        original_image_path = os.path.join(dir_name, original_base_name)
        base_out, ext_out = os.path.splitext(original_base_name)
        output_file_name = f"{base_out}_masked{ext_out}"
        output_masked_path = os.path.join(dir_name, output_file_name)

        if not os.path.isfile(original_image_path):
            log_func(f"\nAVISO: Mapa '{base_seg_name}' encontrado, mas a imagem original '{original_base_name}' não foi localizada. Pulando.")
            continue
             
        arquivos_processados += 1
        log_func(f"\n[Processando]: {original_base_name}")
        log_func(f"  -> Usando mapa de segmentação: {base_seg_name}")
        log_func(f"  -> Saída da imagem mascarada: {output_file_name}")

        try:
            # LÓGICA ROBUSTA PARA ENCONTRAR OS DADOS
            with fits.open(original_image_path) as hdul_original:
                # Tenta ler a imagem da extensão 0, se não der, tenta da 1
                if hdul_original[0].data is not None:
                    data_original = hdul_original[0].data
                    header_original = hdul_original[0].header
                    log_func("  -> Lendo dados da imagem original da extensão [0].")
                elif len(hdul_original) > 1 and hdul_original[1].data is not None:
                    data_original = hdul_original[1].data
                    header_original = hdul_original[1].header
                    log_func("  -> Lendo dados da imagem original da extensão [1].")
                else:
                    raise ValueError("Não foi possível encontrar dados de imagem no arquivo original.")

            with fits.open(seg_map_path) as hdul_seg:
                # Tenta ler o mapa da extensão 1 (caso incomum), se não der, tenta da 0 (padrão)
                if len(hdul_seg) > 1 and hdul_seg[1].data is not None:
                    data_seg = hdul_seg[1].data
                    log_func("  -> Lendo dados do mapa de segmentação da extensão [1].")
                elif hdul_seg[0].data is not None:
                    data_seg = hdul_seg[0].data
                    log_func("  -> Lendo dados do mapa de segmentação da extensão [0].")
                else:
                    raise ValueError("Não foi possível encontrar dados de imagem no mapa de segmentação.")

            if data_original.shape != data_seg.shape:
                log_func(f"  -> ERRO: As dimensões da imagem ({data_original.shape}) e do mapa ({data_seg.shape}) não coincidem.")
                continue

            data_mascarada = np.copy(data_original)
            data_mascarada[data_seg > 0] = 0
            
            fits.writeto(output_masked_path, data_mascarada, header_original, overwrite=True)
            
            log_func(f"  -> SUCESSO! Arquivo mascarado salvo em '{output_file_name}'.")

        except Exception as e:
            log_func(f"  -> ERRO inesperado ao processar '{original_base_name}': {e}")
             
    if arquivos_processados == 0:
        log_func("Nenhum mapa de segmentação novo foi encontrado para processar.")
         
    log_func("\n--- Aplicação de máscaras concluída. ---")


#if __name__ == "__main__":
#    parser = argparse.ArgumentParser(description="Processador de imagens FITS para detecção e mascaramento de fontes.")
#    parser.add_argument("diretorio", help="O diretório alvo que contém as imagens FITS.")
#    parser.add_argument(
#        "tarefa", 
#        choices=['sextractor', 'mask', 'all'], 
#        help="A tarefa a ser executada: 'sextractor' para gerar mapas de segmentação, 'mask' para aplicar as máscaras, ou 'all' para executar ambas em sequência."
#    )
#     
#    args = parser.parse_args()
#    diretorio_alvo = args.diretorio
#    tarefa_escolhida = args.tarefa
#
#    if tarefa_escolhida == 'sextractor':
#        running_Sextractor(diretorio_alvo)
#    elif tarefa_escolhida == 'mask':
#        apply_segmentation_mask(diretorio_alvo)
#    elif tarefa_escolhida == 'all':
#        running_Sextractor(diretorio_alvo)
#        apply_segmentation_mask(diretorio_alvo)