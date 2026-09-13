# The visualization tool -- niiVue 

NiiVue detects eligible daughter arteries that directly originate from the abdominal aorta in CTA volumes.

## Setup
python3 -m pip install -r requirements.txt

## Run

python3 run.py --image data/subject001/orig1.nii --aorta-mask data/subject001/mask1.nii --output prediction.json

The program accepts a CT volume and parent-aorta mask and writes the predicted daughter vessels to `prediction.json`.

The program runs on CPU and requires no manual point placement or case-specific edits.

**To run the website:**
1. Ensure you have [npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) installed
2. In the project directory, run ``cd frontend``
3. Once in the ``frontend`` directory, run ``npm run dev``
