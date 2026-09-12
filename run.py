import argparse  # for the hiddentests where they uppload a ct scan to check code 
def main():
    # will understand the information given by the user 
    parser = argparse.ArgumentParser()  
    # get the CT file 
    parser.add_argument("--image", required=True)
    # get the aorta mask 
    parser.add_argument("--aorta-mask". required=True)
    # get the location where we will save our prediciton 
    parser.add_argument("--output", required=True)
    # to save the result as json 
    args=parser.parse_args() 
    # store the ct file, mask and output in these variables 
    image_path = args.image  
    mask_path = args.aorta_mask 
    output_path = args.output 
    
    # 1. Load CT
    # 2. Load aorta mask
    # 3. Detect branches
    # 4. Analyze branches
    # 5. Generate JSON
    # 6. Save prediction

if __name__ == "__main__":
    main()
