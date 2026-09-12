import argparse  # for the hiddentests where they uppload a ct scan to check code 
from src.io import load_nifti_image, get_image_array
def main():
    # will understand the information given by the user 
    parser = argparse.ArgumentParser()  
    # get the CT file 
    parser.add_argument("--image", required=True)
    # get the aorta mask 
    parser.add_argument("--aorta-mask", required=True)
    # get the location where we will save our prediciton 
    parser.add_argument("--output", required=True)
    # to save the result as json 
    args=parser.parse_args() 
    # store the ct file, mask and output in these variables 
    image_path = args.image  
    mask_path = args.aorta_mask 
    output_path = args.output 
    # load CT and aorta mask 
    ct_image = load_nifti_image(image_path)
    mask_image= load_nifti_image(mask_path)
    ct_array= get_image_array(ct_image)
    mask_array= get_image_array(mask_image) 
    # to test 
    print("CT shape:", ct_array.shape)
    print("Mask shape:", mask_array.shape) 

    # 3. Detect branches
    # 4. Analyze branches
    # 5. Generate JSON
    # 6. Save prediction

if __name__ == "__main__":
    main()
