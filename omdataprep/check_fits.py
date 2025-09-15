import os
import glob
from astropy.io import fits

def sincronizar_wcs_de_fits(diretorio):
    """
    Sincroniza os parâmetros WCS de um arquivo FITS de referência para um arquivo de destino
    dentro de um diretório específico.

    A função procura por dois arquivos FITS com padrões de nome específicos. Se o arquivo
    de referência (SIMAGE) tiver o filtro 'UVW1', a função compara seis parâmetros
    WCS (CRPIX1, CRVAL1, CDELT1, CRPIX2, CRVAL2, CDELT2) com o arquivo de destino.
    Se houver qualquer diferença, os parâmetros do arquivo de destino são atualizados
    com os valores do arquivo de referência.

    Args:
        diretorio (str): O caminho para o diretório onde os arquivos FITS estão localizados.

    Returns:
        None
    """

    # Padrão para o arquivo de origem (de onde vamos ler os parâmetros)
    padrao_origem = os.path.join(diretorio, 'P*OMS0*SIMAGE1000.FIT')
    # Padrão para o arquivo de destino (que talvez precisemos atualizar)
    padrao_destino = os.path.join(diretorio, 'P*OMS0*IMAGE_1000_jpiter_filtred_rotated_WCS.FIT')

    arquivos_origem = glob.glob(padrao_origem)
    arquivos_destino = glob.glob(padrao_destino)

    if not arquivos_origem:
        print(f"AVISO: Nenhum arquivo de origem encontrado com o padrão '{os.path.basename(padrao_origem)}'")
        return
    if not arquivos_destino:
        print(f"AVISO: Nenhum arquivo de destino encontrado com o padrão '{os.path.basename(padrao_destino)}'")
        return

    arquivo_origem_path = arquivos_origem[0]
    arquivo_destino_path = arquivos_destino[0]

    print(f"Arquivo de Origem encontrado: {os.path.basename(arquivo_origem_path)}")
    print(f"Arquivo de Destino encontrado: {os.path.basename(arquivo_destino_path)}")


    with fits.open(arquivo_origem_path) as hdul_origem:
        header_origem = hdul_origem[0].header

        if 'FILTER' not in header_origem:
            print(f"ERRO: O arquivo de origem '{os.path.basename(arquivo_origem_path)}' não contém a palavra-chave 'FILTER'.")
            return

        if header_origem['FILTER'].strip().upper() != 'UVW1':
            print(f"INFO: O filtro do arquivo de origem é '{header_origem['FILTER']}', não 'UVW1'. Nenhuma ação será tomada.")
            return

        print("INFO: Filtro UVW1 confirmado no arquivo de origem.")

        parametros_wcs = [
            'CRPIX1', 'CRVAL1', 'CDELT1',
            'CRPIX2', 'CRVAL2', 'CDELT2'
        ]
        valores_origem = {}
        try:
            for param in parametros_wcs:
                valores_origem[param] = header_origem[param]
        except KeyError as e:
            print(f"ERRO: O header do arquivo de origem não contém o parâmetro obrigatório: {e}")
            return


    with fits.open(arquivo_destino_path, mode='update') as hdul_destino:
        header_destino = hdul_destino[0].header
        precisa_atualizar = False

        print("\n--- Comparando Parâmetros WCS ---")
        for param in parametros_wcs:
            if param not in header_destino or header_destino[param] != valores_origem[param]:
                if param in header_destino:
                    print(f"DIFERENÇA encontrada em '{param}': Origem={valores_origem[param]}, Destino={header_destino[param]}")
                else:
                    print(f"AVISO: Parâmetro '{param}' ausente no destino. Será adicionado.")
                precisa_atualizar = True
                header_destino[param] = valores_origem[param]
            else:
                print(f"'{param}' está igual em ambos os arquivos.")


        if precisa_atualizar:
            hdul_destino.flush()
            print("\nSUCESSO: O header do arquivo de destino foi atualizado!")
        else:
            print("\nINFO: Todos os parâmetros WCS já estavam sincronizados. Nenhuma alteração foi necessária.")
