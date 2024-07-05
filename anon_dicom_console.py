#%%
import pydicom
import pydicom.charset
import pydicom.config
from pydicom import compat
from pydicom._version import __version_info__
from pydicom.charset import default_encoding, convert_encodings
from pydicom.config import logger
from pydicom.datadict import dictionary_VR
from pydicom.datadict import (tag_for_keyword, keyword_for_tag, repeater_has_keyword)
from pydicom.dataelem import DataElement, DataElement_from_raw, RawDataElement
from pydicom.pixel_data_handlers.util import (convert_color_space, reshape_pixel_array)
import pydicom.pixel_data_handlers.gdcm_handler as gdcm_handler
from pydicom.pixel_data_handlers import gdcm_handler, pillow_handler
from pydicom.tag import Tag, BaseTag, tag_in_exception
from pydicom.uid import (ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian,
                         PYDICOM_IMPLEMENTATION_UID)
import os
import argparse
from datetime import date
from copy import deepcopy
import configparser
import pandas as pd
import re
import hashlib


#####################################################
# USEFUL FUNCTIONS

# To replace multiple elements
def replace_multiple(main_string, to_be_replaces, new_string):
    # Iterate over the strings to be replaced
    for elem in to_be_replaces:
        # Check if string is in the main string
        if elem in main_string:
            # Replace the string
            main_string = main_string.replace(elem, new_string)
    return main_string


# To remove weird chars
def to_pretty_string(string_to_prettify):
    string_to_prettify = replace_multiple(string_to_prettify, [":", "*", "/", "\\", "\"", "<", ">", "|", "?"], "")
    string_to_prettify = replace_multiple(string_to_prettify, ["^"], " ")
    return string_to_prettify

def prettyHex(input_int, return_str=0):
    """Convert a base10 int or short hex to a full hex
    e.g. 0x10 --> 0x0010, or 16 --> 0x0010

    Args:
        input_int (int): input int

    Raises:
        TypeError: if you fed it something else

    Returns:
        _type_: _description_
    """
    if not type(input_int) == int:
        raise TypeError("Please input a hex or integer, not a string.")
    
    value = input_int
    padding = 6

    if return_str:
        return str(f"{value:#0{padding}x}")
    else:
        return f"{value:#0{padding}x}"


# PLEASE REMOVE EVENTUALLY
test_dicom = r"C:\Users\Covie\OneDrive\Documents\Work\Research\Parotid ESHNR\Data Flow\DicomAnon\Hip fx\Anon.Seq1.Ser1.Img1.dcm"
test_dicom_folder = r"C:\Users\Covie\OneDrive\Documents\Work\Research\Parotid ESHNR\Data Flow\DicomAnon\Hip fx\\"

#####################################################

# DICOM Elements:
# https://dicom.nema.org/medical/dicom/current/output/chtml/part06/chapter_6.html#table_6-1

tags_to_remove_default = {
    "Patient Birth Date": [0x0010, 0x0030],
    "Referrer": [0x0008, 0x0090],
    "Patient Address": [0x0010, 0x1040],
    "Patient Weight": [0x0010, 0x1030],
    "Patient Age": [0x0010, 0x1010],
    "Patient Sex": [0x0010,0x0040],
    "Medical Alerts": [0x0010,0x2000],
    "Issuer of Patient ID": [0x0008, 0x0021],
    "Study Date": [0x0008, 0x0020],
    "Study Time": [0x0008, 0x0030],
    "Station Name": [0x0008, 0x1010],
    "Operator Name": [0x0008, 0x1070],
    "Institution Address": [0x0008, 0x0081],
    "Institution Name": [0x0008, 0x0080],
    "Referrer Address": [0x0008, 0x0092],
    "Referrer Telephone": [0x0008, 0x0094],
    "Physicians of Record": [0x0008, 0x1048],
    "Performing Physician": [0x0008, 0x1050],
    "Referring Physician Name": [0x0008, 0x1050],
}

# To Replace:
# - Name      (0x0010, 0x0010)
# - ID        (0x0010, 0x0020)
# - Accession (0x0008, 0x0050)

def processHexStr(input_str):
    re_full = re.match(r'\((0x\S+),\s?(0x\S+)\)', input_str)
    return [re_full[1], re_full[2]]

def createReadConfig():
    config_ini_path = os.path.join(os.getcwd(), 'tags.ini')
    config = configparser.ConfigParser()

    if os.path.exists(config_ini_path):
        # If the config file exists, read it and return the dict
        config.read('tags.ini')
        tags_config = config['TAGS_TO_REMOVE']
        dict_tags = dict(tags_config)
        for k in dict_tags.keys():
            dict_tags[k] = processHexStr(dict_tags[k])
        
        return dict_tags
    else:
        config['TAGS_TO_REMOVE'] = {}
        for k in tags_to_remove_default.keys():
            first_val= int(tags_to_remove_default[k][0])
            second_val = int(tags_to_remove_default[k][1])
            dcm_tag_str = f"({prettyHex(first_val)}, {prettyHex(second_val)})"
            config['TAGS_TO_REMOVE'][k] = dcm_tag_str
        with open('tags.ini', 'w') as configfile:
            config.write(configfile)



#####################################################

def followDataType(dcm_elem):
    """Check the datatype of the tag, then return the according value

    DS: 0.0
    DA: 20000101
    TM: 000000
    DT: 946656000.0
    Rest: None

    Args:
        dcm_elem: Pydicom Dataset DataElement
    """

    if dcm_elem.VR == 'DS':
        return '0.0'
    elif dcm_elem.VR == 'DA':
        return '20000101'
    elif dcm_elem.VR == 'TM':
        return '000000'
    elif dcm_elem.VR == 'DT':
        return '946656000.0'
    else:
        return None

#%%
def anonOneDataset(in_dataset, tags_to_remove, name_to_replace, acc_to_replace):
    """Anonymises the dataset according to the respective tags as defined
    Outputs an anonymised copy of the dataset

    Args:
        in_dataset (pydicom dataset): _description_
        name_to_replace(str): Name/IC to substitute
        acc_to_replace(str): Accession no to substitute
    """

    in_dataset_copy = deepcopy(in_dataset)

    for i, dcm_tag in tags_to_remove.items():
        try:
            tag_name = in_dataset_copy[dcm_tag[0], dcm_tag[1]].name
        except KeyError:
            pass
        else:
            in_dataset_copy[dcm_tag[0], dcm_tag[1]].value = followDataType(in_dataset[dcm_tag[0], dcm_tag[1]])

    # Replace the name, IC and accession respectively
    in_dataset_copy[0x0010, 0x0010].value = name_to_replace
    in_dataset_copy[0x0010, 0x0020].value = name_to_replace
    in_dataset_copy[0x0008, 0x0050].value = acc_to_replace

    return in_dataset_copy

def anonUS(dataset):
    # If it is an UltraSound, remove part of the image
    # INCOMPLETE
    if dataset.Modality == "US":
        if dataset.file_meta.TransferSyntaxUID.is_compressed:
            dataset.decompress()
        dataset.pixel_data_handlers = [gdcm_handler, pillow_handler]
        data = dataset.pixel_array
        xmin = dataset.SequenceOfUltrasoundRegions[0].RegionLocationMinX0
        xmax = dataset.SequenceOfUltrasoundRegions[0].RegionLocationMaxX1

        ymin = dataset.SequenceOfUltrasoundRegions[0].RegionLocationMinY0
        ymax = dataset.SequenceOfUltrasoundRegions[0].RegionLocationMaxY1
        ywidth = ymax - xmin
        xwidth = xmax - ymin

        dataset.Rows = ywidth
        dataset.Columns = xwidth
        data2 = data[xmin:ymax, ymin:xmax, :]
        dataset.PixelData = data2.tobytes()
    
    return dataset

def getDataToStrip(in_dataset, tags_to_remove):
    """Saves the data to be stripped in the anonymisation process for future reference
    """
    temp_dict = {}

    temp_dict[in_dataset[0x0010, 0x0010].name] = in_dataset[0x0010, 0x0010].value
    temp_dict[in_dataset[0x0010, 0x0020].name] = in_dataset[0x0010, 0x0020].value
    temp_dict[in_dataset[0x0008, 0x0050].name] = in_dataset[0x0008, 0x0050].value

    for i, dcm_tag in tags_to_remove.items():
        try:
            tag_name = in_dataset[dcm_tag[0], dcm_tag[1]].name
        except KeyError:
            pass
        else:
            temp_dict[tag_name] = in_dataset[dcm_tag[0], dcm_tag[1]].value
    
    return temp_dict

def anonOneDicom(dicom_str, tags_to_remove):
    """Anonymises one DICOM file
    Returns a dict: {
        "dataset": dataset,
        "anon_values": dict_anon_values
    }
    """

    dataset = pydicom.dcmread(dicom_str)
    dict_pre_anon = getDataToStrip(dataset, tags_to_remove)
    id_anon = hashlib.shake_256(dataset.PatientID.encode()).hexdigest(5)
    dataset_anon = anonOneDataset(dataset,tags_to_remove, id_anon, dataset.AccessionNumber)

    return {
        "dataset": dataset_anon,
        "anon_values": dict_pre_anon
    }

def returnFolderAnon(dcm_file, output_path=""):
    """Given a path to a .dcm file, this fn returns the path to the anonymised file
    e.g. C:\dcm_files\Anon.Ser1.Im1.dcm >>
         C:\dcm_files_anon\Anon.Ser1.Im1.dcm

    Args:
        dcm_file (os.path string): Input file

    Raises:
        TypeError: Break if the file is not a .dcm
    """
    if not dcm_file.endswith(".dcm"):
        # Break if the file is not a .dcm
        raise TypeError("File is not a .dcm file")
    
    dcm_path = os.path.dirname(dcm_file)
    dcm_filename = os.path.basename(dcm_file)
    folder_name = os.path.basename(dcm_path)
    # Set the folder name for the final anonymised files
    # If the folder name is set, then use it. Otherwise use the default path
    if output_path:
        if os.path.exists(output_path):
            folder_root = output_path
        else:
            raise LookupError("Invalid path supplied. Please check?")
    else:
        folder_root = os.path.dirname(dcm_path)
    folder_name_anon = folder_name + "_anon"

    return os.path.join(folder_root, folder_name_anon, dcm_filename)

def listAllFiles(start_path='.'):
    output_lst = []
    for root, dirs, files in os.walk(start_path):
        for file in files:
            output_lst.append(os.path.join(root, file))
    
    return output_lst

def processIndex(index_dict, filename):
    index_df = pd.DataFrame(index_dict).transpose().drop_duplicates()
    index_df["Patient's Name"].astype(str)
    index_df.to_csv(filename)

def anonFolder(folder, output_path="", console_mode=0):
    """Anonymise one folder, or a recursive selection of folders.
    Outputs each subfolder to subfolder_anon
    e.g. C:\dcm_files\Anon.Ser1.Im1.dcm >>
         C:\dcm_files_anon\Anon.Ser1.Im1.dcm

    Args:
        folder (str): _description_
        console_mode (int, optional): Are we running in a console? Defaults to 0.

    Returns:
        Dictionary of the keys of the anonymised files
    """

    tags_to_remove = createReadConfig()

    # First get all the DICOM files in the folder
    list_of_files = listAllFiles(folder)
    list_of_dcm = [f for f in list_of_files if f.endswith("dcm")]
    dict_anon_index = {}

    if console_mode:
        print(f"Found {len(list_of_dcm)} files")

    # Then loop and anonymise accordingly

    ###
    # Do we need to check if it's a screensave???
    # To do this, check study description
    # if studyDescription != "unnamedStudy":
    #   ...
    ###

    for f in list_of_dcm:
        if console_mode:
            # Print: [1/3] Anonymising file: Anon.Seq1.Ser1.Img1.dcm ... 
            print(f"[{list_of_dcm.index(f)+1}/{len(list_of_dcm)}] Anonymising file: {os.path.basename(f)}", end=" ... ")

        dict_anon_return = anonOneDicom(f, tags_to_remove)
        dataset = dict_anon_return['dataset']
        dict_anon_index[dataset.PatientID] = dict_anon_return["anon_values"]

        # Check if directory exists
        anon_ds_loc = returnFolderAnon(f, output_path)
        anon_ds_path = os.path.dirname(anon_ds_loc)
        if not os.path.exists(anon_ds_path):
            os.makedirs(anon_ds_path)

            if console_mode:
                print("Creating dir", end=" ... ")

        # Save the dataset    
        dataset.save_as(anon_ds_loc)

        if console_mode:
            print(f"Success! Saved to {returnFolderAnon(f)}")

        processIndex(dict_anon_index, "anon_index.csv")
        
    return dict_anon_index

############################################################################

#%%
# Now for the console part

def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('-input', '-i', help='Path to the input directory which contains dicom files (.dcm). Does not work on DICOMDIR at present.')
    parser.add_argument('-output', '-o', help='(Optional) Path to the output directory (must be a valid path).')
    args = parser.parse_args()

    input_dicom_path = args.input
    output_dicom_path = args.output
    
    anonFolder(input_dicom_path, output_dicom_path, console_mode=1)

if __name__ == "__main__":
    main()
# %%
