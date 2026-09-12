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
