import pandas as pd
import re
from datetime import datetime
import streamlit as st
from io import BytesIO
import zipfile

# Define the headers
HEADERS_LTE = [
    "EPC", "SITE", "NAME", "ALTITUDE", "SECTOR", "HEIGHT", "BEAMDIRECTION", "MTILT", "ETILT", "GEODATUM",
    "LATITUDE", "LATHEMISPHERE", "LONGITUDE", "LONGHEMISPHERE", "RET", "ATTENUATION", "DELAY", "ANTENNATYPE",
    "CELL", "BPLMNLIST", "BPLMNLIST_MNC", "TAC", "ENODEBID", "CELLID", "PCI", "PCIG", "PSCI", "CONFOUTPUTPOWER",
    "PARTOFRADIOPOWER", "CHANNEL_NO_UL", "CHANNEL_NO_DL", "UL_BANDWIDTH", "DL_BANDWIDTH", "RACHROOTSEQUENCE",
    "CSFALLBACKPRIOGERAN", "CSFALLBACKPRIOUTRAN", "GSMFREQGROUPID", "TMA", "RRU", "TXANTENNAS", "RXANTENNAS",
    "SECONDARYANTENNAS", "VFID"
]

HEADERS_NR = [
    "MECONTEXT", "FUNCTION", "CELL", "CELLID", "CHANNEL_NO_DL", "CHANNEL_NO_UL", "TAC", "PCI", "CONFOUTPUTPOWER",
    "RACHROOTSEQUENCE", "DL_BANDWIDTH", "UL_BANDWIDTH", "TXANTENNAS", "RXANTENNAS", "BEAMDIRECTION", "MTILT", "ETILT",
    "GEODATUM", "LATITUDE", "LATHEMISPHERE", "LONGITUDE", "LONGHEMISPHERE", "RRU", "ANTENNATYPE", "SECONDARYANTENNAS", "RET", "VFID"
]

def parse_txt_file(txt_file):
    site = ""  # To store SITE value
    data_lte = []   # List to store parsed LTE data
    data_nr = []    # List to store parsed NR data
    power_data = {}  # Dictionary to store sectorCarrierId mappings
    
    # with open(txt_file, "r", encoding="utf-8") as file:
    #     lines = file.readlines()

    lines = txt_file.read().decode("utf-8").splitlines()

    # Extract SITE value
    for i, line in enumerate(lines):
        if "MO              ;eNodeBFunctionId" in line:
            site = lines[i + 1].split(";")[2].strip()
            break
        elif "MO              ;gNBDUFunctionId" in line:
            site = lines[i + 1].split(";")[2].strip()
            break

    #Extract RRU from sdir
    rru_mapping = {}
    parsing_rru = False

    for line in lines:
        if "FRU" in line and "Sector/AntennaGroup/Cells" in line:
            parsing_rru = True
            continue
        
        if parsing_rru and line.strip():
            parts = line.split(";")
            if len(parts) >= 10:
                board = parts[2].strip()  # BOARD value
                sector_info = parts[9].strip()
                
                # Extract cell IDs from the sector info
                cell_matches = re.findall(r'([A-Z0-9]+)', sector_info)
                #print(cell_matches)
                
                for cell_id in cell_matches:
                    rru_mapping[cell_id] = board

    # Extract power data from the third table
    parsing_power = False
    for line in lines:
        if line.startswith("MO                   ;configuredMaxTxPower"):
            parsing_power = True
            continue
        
        if parsing_power and "SectorCarrier=" in line:
            parts = line.split(";")
            if len(parts) >= 5:
                power_data[parts[4].strip()] = {
                    "CONFOUTPUTPOWER": parts[1].strip(),
                    "TXANTENNAS": parts[3].strip(),
                    "RXANTENNAS": parts[2].strip()
                }
    
    # Extract data from the second table
    parsing = False
    for line in lines:
        if line.startswith("MO                   ;cellId"):
            parsing = True
            continue
        
        if parsing and "EUtranCellFDD=" in line:
            parts = line.split(";")
            if len(parts) >= 11:
                cell_id = parts[3].strip()
                data_lte.append({
                    "SITE": site,
                    "CELL": cell_id,
                    "TAC": parts[10],
                    "CELLID": parts[1],
                    "PCI": parts[6],
                    "PCIG": parts[7],
                    "PSCI": parts[8],
                    "CHANNEL_NO_UL": parts[5],
                    "CHANNEL_NO_DL": parts[4],
                    "UL_BANDWIDTH": parts[11],
                    "DL_BANDWIDTH": parts[2],
                    "RACHROOTSEQUENCE": parts[9],
                    "CONFOUTPUTPOWER": power_data.get(cell_id, {}).get("CONFOUTPUTPOWER", ""),
                    "TXANTENNAS": power_data.get(cell_id, {}).get("TXANTENNAS", ""),
                    "RXANTENNAS": power_data.get(cell_id, {}).get("RXANTENNAS", ""),
                    "SECTOR": site + "S" + parts[1],
                    "GEODATUM": "DHDN",
                    "LATHEMISPHERE" : "N",
                    "LONGHEMISPHERE" : "E",
                    "ENODEBID" : "null",
                    "GSMFREQGROUPID" : "10",
                    "BPLMNLIST": "262",
                    "BPLMNLIST_MNC" : "2",
                    "ATTENUATION" : "0",
                    "DELAY" : "0",
                    "RRU": rru_mapping.get(cell_id, "Unknown") 
                })
    
    # Extract data from the fourth table (NB-IoT cells)
    parsing_nbiot = False
    for line in lines:
        if line.startswith("MO               ;availabilityStatus"):
            parsing_nbiot = True
            continue
        
        if parsing_nbiot and "NbIotCell=" in line:
            parts = line.split(";")
            if len(parts) >= 5:
                cell_id = parts[3].strip()
                pci_value = int(parts[4].strip())
                data_lte.append({
                    "SITE": site,
                    "CELL": cell_id,
                    "TAC": parts[5].strip(),
                    "CELLID": parts[2].strip(),
                    "PCI": parts[4].strip(),
                    "PCIG": str(pci_value // 3),
                    "PSCI": str(pci_value % 3),
                    "CHANNEL_NO_UL": "6346",
                    "CHANNEL_NO_DL": "24346",
                    "UL_BANDWIDTH": "1400",
                    "DL_BANDWIDTH": "1400",
                    "RACHROOTSEQUENCE": "100",
                    "CONFOUTPUTPOWER": "3170",
                    "TXANTENNAS": "2",
                    "RXANTENNAS": "2",
                    "SECTOR": site + "S" + parts[2],
                    "GEODATUM": "DHDN",
                    "LATHEMISPHERE" : "N",
                    "LONGHEMISPHERE" : "E",
                    "ENODEBID" : "null",
                    "GSMFREQGROUPID" : "10",
                    "BPLMNLIST": "262",
                    "BPLMNLIST_MNC" : "2",
                    "ATTENUATION" : "0",
                    "DELAY" : "0",
                    "RRU": rru_mapping.get(cell_id, "Unknown") 
                })

    function = ""
    for i, line in enumerate(lines):
        if "MO             ;gNBDUFunctionId" in line:
            function = lines[i + 1].split(";")[2].strip()
            break
    
    # Extract NR Cell Data
    parsing_nr = False
    for line in lines:
        if line.startswith("MO              ;cellLocalId"):
            parsing_nr = True
            continue
        
        if parsing_nr and "NRCellDU=" in line:
            parts = line.split(";")
            if len(parts) >= 5:
                data_nr.append({
                    "MECONTEXT": function,
                    "FUNCTION": function,
                    "CELL": parts[2].strip(),
                    "CELLID": parts[1].strip(),
                    "TAC": parts[4].strip(),
                    "PCI": parts[3].strip(),
                    "RACHROOTSEQUENCE": parts[5].strip(),
                    "MTILT" : "0",
                    "GEODATUM" : "DHDN",
                    "LATHEMISPHERE" : "N",
                    "LONGHEMISPHERE" : "E",
                    "SECONDARYANTENNAS" : "NONE", 
                    "RRU": rru_mapping.get(parts[2].strip(), "Unknown") 
                })
    
    # Extract NR Sector Carrier Data
    parsing_sector = False
    for line in lines:
        if line.startswith("MO                     ;arfcnDL"):
            parsing_sector = True
            continue
        
        if parsing_sector and "NRSectorCarrier=" in line:
            parts = line.split(";")
            if len(parts) >= 7:
                for item in data_nr:
                    if item["CELL"] in parts[0]:
                        item.update({
                            "CHANNEL_NO_DL": parts[1].strip(),
                            "CHANNEL_NO_UL": parts[2].strip(),
                            "DL_BANDWIDTH": parts[3].strip(),
                            "UL_BANDWIDTH": parts[4].strip(),
                            "CONFOUTPUTPOWER": parts[5].strip(),
                            "RXANTENNAS": parts[6].strip(),
                            "TXANTENNAS": parts[7].strip()
                        })

    return site, function, data_lte, data_nr

def generate_zip_download(site, function, data_lte, data_nr):
    date_str = datetime.now().strftime("%Y%m%d")
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if data_lte:
            lte_bytes = BytesIO()
            with pd.ExcelWriter(lte_bytes, engine='openpyxl') as writer:
                df_lte = pd.DataFrame(data_lte, columns=HEADERS_LTE)
                df_lte.to_excel(writer, sheet_name='LTE', index=False)
            lte_bytes.seek(0)
            zipf.writestr(f"{site}_LTE_{date_str}.xlsx", lte_bytes.read())

        if data_nr:
            site = function
            nr_bytes = BytesIO()
            with pd.ExcelWriter(nr_bytes, engine='openpyxl') as writer:
                df_nr = pd.DataFrame(data_nr, columns=HEADERS_NR)
                df_nr.to_excel(writer, sheet_name='NR', index=False)
            nr_bytes.seek(0)
            zipf.writestr(f"{site}_NR_{date_str}.xlsx", nr_bytes.read())

    zip_buffer.seek(0)
    zip_filename = f"{site}_RadioData_{date_str}.zip"
    return zip_buffer, zip_filename

st.title('Radiodata Generator from Log')
st.divider()
st.write("Copy below command to your moshell")

moshell_script = """
hgetc enodebfunction=1 enodebfunctionid$|^userlabel$
hgetc EUtranCellFDD ^eUtranCellFDDId$|^tac$|^cellId$|^physicalLayerCellId$|^physicalLayerCellIdGroup$|^physicalLayerSubCellId$|^earfcnul$|^earfcndl$|^ulChannelBandwidth$|^dlChannelBandwidth$|^rachRootSequence$
hgetc sectorcarrier ^sectorcarrierid$|^configuredMaxTxPower$|^noOfTxAntennas$|^noOfRxAntennas$
hgetc nbiot ^cellid$|^arfcn$|^availabilityStatus$|^nbIotCellId$|^tac$|^physicalLayerCellId$
hgetc gnbdufunction=1 ^gnbdufunctionid$|^userlabel$
hgetc nrcelldu ^nrcellduid$|^cellLocalId$|^nRTAC$|^nRPCI$|^rachRootSequence$
hgetc nrsectorcarrier ^arfcn|^bSChannelBw|^noOfTxAntennas$|^noOfRxAntennas$|^configuredmaxtxpower$
sdir
"""

st.expander("MOS Script").code(moshell_script)
st.divider()

result_bytes = None
download_filename = None

log_moshell = st.file_uploader("Upload a TXT file", accept_multiple_files=False)
if log_moshell is not None:
    site, function, data_lte, data_nr = parse_txt_file(log_moshell)
    result_bytes, download_filename = generate_zip_download(site, function, data_lte, data_nr)

if result_bytes is not None and download_filename is not None:
    st.download_button(
        label="Download ZIP of Processed Files",
        data=result_bytes,
        file_name=download_filename,
        mime="application/zip"
    )




