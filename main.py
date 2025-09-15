from omdataprep import *
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
'''
Antes de rodar coloque no terminal:
. /net/ASTRO/ricardomarzall/sas/sas_22/xmmsas_22.1.0-a8f2c2afa-20250304/initsas.sh
heainit
'''

def main():
    """Pipeline principal para download, extração e processamento OM.
    Execute após ativar o ambiente SAS e heainit.
    """
    # Parâmetros para o download
    csv_file_path = "/net/ASTRO/ricardomarzall/Documentos/Diffuse_Emission_UV/sample_selectio/subsamble_with_redshift.csv"
    destination_directory = "/net/ASTRO/ricardomarzall/Documentos/WD/OM/BASE_PARA_TESTES_CODIGO/lixo"
    aioclient_path = "/net/ASTRO/ricardomarzall/aioclient/nxsa-cl-aioclient"
    start = 1
    end = 2
    instname = "OM"
    filter_name = "UVW1 UVM2"
    # Download
    downloader = Download(csv_file_path, destination_directory, aioclient_path, start, end, instname, filter_name)
    downloader.carregar_csv()
    downloader.baixar_observacoes()
    # Extração dos arquivos baixados
    extractor = Extract(destination_directory, True)
    extractor.extract_and_organize()
    # Running Omichain
    RunOmichain(destination_directory, '/net/ASTRO/ricardomarzall/sas/sas_22/xmmsas_22.1.0-a8f2c2afa-20250304/initsas.sh', False, False)

if __name__ == '__main__':
    main()