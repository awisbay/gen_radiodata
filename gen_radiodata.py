import pandas as pd
import re
from datetime import datetime
import sys

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

def extract_rru_mapping(lines):
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
                cell_matches = re.findall(r'\((?:\d+:)?(\d+):\d+\)', sector_info)
                
                for cell_id in cell_matches:
                    rru_mapping[cell_id] = board
    
    return rru_mapping

def parse_txt_file(txt_file):
    site = ""  # To store SITE value
    data_lte = []   # List to store parsed LTE data
    data_nr = []    # List to store parsed NR data
    power_data = {}  # Dictionary to store sectorCarrierId mappings
    
    with open(txt_file, "r", encoding="utf-8") as file:
        lines = file.readlines()

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
            if len(parts) >= 15:
                cell_id = parts[4].strip()
                data_lte.append({
                    "SITE": site,
                    "CELL": cell_id,
                    "TAC": parts[13],
                    "CELLID": parts[1],
                    "PCI": parts[7],
                    "PCIG": parts[8],
                    "PSCI": parts[9],
                    "CHANNEL_NO_UL": parts[6],
                    "CHANNEL_NO_DL": parts[5],
                    "UL_BANDWIDTH": parts[14],
                    "DL_BANDWIDTH": parts[2],
                    "RACHROOTSEQUENCE": parts[12],
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
        if line.startswith("MO               ;attachWithoutPDNConnectivityList"):
            parsing_nbiot = True
            continue
        
        if parsing_nbiot and "NbIotCell=" in line:
            parts = line.split(";")
            if len(parts) >= 8:
                cell_id = parts[6].strip()
                pci_value = int(parts[7].strip())
                data_lte.append({
                    "SITE": site,
                    "CELL": cell_id,
                    "TAC": parts[8].strip(),
                    "CELLID": parts[2].strip(),
                    "PCI": parts[7].strip(),
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
            if len(parts) >= 6:
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

def save_to_excel(site, function, data_lte, data_nr):
    date_str = datetime.now().strftime("%Y%m%d")
    
    if data_lte:
        df_lte = pd.DataFrame(data_lte, columns=HEADERS_LTE)
        output_file_lte = f"{site}_Radiodata_LTE_{date_str}.xlsx"
        df_lte.to_excel(output_file_lte, index=False)
    
    if data_nr:
        df_nr = pd.DataFrame(data_nr, columns=HEADERS_NR)
        output_file_nr = f"{function}_Radiodata_NR_{date_str}.xlsx"
        df_nr.to_excel(output_file_nr, index=False)

# Usage
input_txt = sys.argv[1]  # Get the input file from command-line
#input_txt = "log.txt"
site, function, parsed_data_lte, parsed_data_nr = parse_txt_file(input_txt)
save_to_excel(site, function, parsed_data_lte, parsed_data_nr)
