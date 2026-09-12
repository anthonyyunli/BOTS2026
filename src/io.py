'''
handles medical imaging files- use SimpleITK

So this file handles things like:
image = sitk.ReadImage(...)
mask = sitk.ReadImage(...)

array = sitk.GetArrayFromImage(image)
and importantly, keeps track of:
spacing
origin
direction
physical coordinates
'''
import SimpleITK as sitk
import numpy as np

def load_nifti_image(file_path):
    """
    Loads NIFTI image files using SimpleITK
    """
    image = sitk.ReadImage(file_path)
    return image

def get_image_array(sitk_image):
    """
    Extracts the image data as a NumPy array"
    """
    image_array = sitk.GetArrayFromImage(sitk_image)
    return image_array

def get_image_metadata(sitk_image):
    """
    extracts the physical metadata from a SimpleITK iamge
    """
    metadata = {
        "spacing": sitk_image.GetSpacing(),
        "origin": sitk_image.GetOrgin(),
        "direction": sitk_image.GetDirection()
    }

    return metadata

def index_to_phsycial(sitk_image, voxel_index):
    """
    converts a voxel index (x, y, z) to physical coordinates (mm)
    """
    physical_point = sitk_image.IndexToPhysicalPoint(voxel_index)
    return physical_point


    
import os
if __name__ == "__main__":
    print("Hunting for the exact file location...")
    
    # Start searching from the directory you run the terminal in
    search_dir = os.getcwd()
    found_ct = None
    found_mask = None
    
    # Walk through all folders and subfolders dynamically
    for root, dirs, files in os.walk(search_dir):
        for file in files:
            if file == "orig1.nii":
                found_ct = os.path.join(root, file)
            elif file == "mask1.nii":
                found_mask = os.path.join(root, file)

    if found_ct and found_mask:
        print(f"FOUND CT AT: {found_ct}")
        print(f"FOUND MASK AT: {found_mask}")
        
        try:
            # Load the images
            ct_image = sitk.ReadImage(found_ct)
            mask_image = sitk.ReadImage(found_mask)
            
            # Print sizes
            ct_size = os.path.getsize(found_ct) / (1024 * 1024)
            print(f"CT loaded successfully! Size: {ct_size:.2f} MB")
            
            # Get the arrays to confirm shape
            ct_array = sitk.GetArrayFromImage(ct_image)
            mask_array = sitk.GetArrayFromImage(mask_image)
            print(f"CT Array shape (z, y, x): {ct_array.shape}")
            print(f"Mask Array shape (z, y, x): {mask_array.shape}")
            
        except Exception as e:
            print(f"SimpleITK Error: {e}")
    else:
        print("Still couldn't find the files. Are you sure they are inside this folder?")
