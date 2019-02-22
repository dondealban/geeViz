import sys,os
sys.path.append('C:/USFS/modules')
os.chdir('C:/USFS/modules')
from getImagesLib import *
#########################################################################

# /***** End of imports. If edited, may not auto-convert in the playground. *****/
# //Module imports
# var getImageLib = require('users/USFS_GTAC/modules:getImagesLib.js');
#########################################################################
#Define user parameters:

#1. Specify study area: Study area
#Can specify a country, provide a fusion table  or asset table (must add 
#.geometry() after it), or draw a polygon and make studyArea = drawnPolygon

geometry = ee.Geometry.Polygon(\
        [[[-116.29374999999999, 46.54729956447318],\
          [-116.03007812499999, 38.809492348693325],\
          [-85.26835937499999, 37.63572230181635],\
          [-77.09453124999999, 47.565183593175995]]])
studyArea = geometry

#2. Update the startJulian and endJulian variables to indicate your seasonal 
#constraints. This supports wrapping for tropics and southern hemisphere.
#startJulian: Starting Julian date 
#endJulian: Ending Julian date
startJulian = 200
endJulian = 200+16

#3. Specify start and end years for all analyses
#More than a 3 year span should be provided for time series methods to work 
#well. If using Fmask as the cloud/cloud shadow masking method, this does not 
#matter
startYear = 2018
endYear = 2018

#4. Specify an annual buffer to include imagery from the same season 
#timeframe from the prior and following year. timeBuffer = 1 will result 
#in a 3 year moving window
timebuffer = 0

# 5. Specify the weights to be used for the moving window created by timeBuffer
#For example- if timeBuffer is 1, that is a 3 year moving window
#If the center year is 2000, then the years are 1999,2000, and 2001
#In order to overweight the center year, you could specify the weights as
#[1,5,1] which would duplicate the center year 5 times and increase its weight for
#the compositing method
weights = [1]


#6. Set up Names for the export
outputName = 'Median-MODIS'

# 7. Provide location composites will be exported to
#This should be an asset folder, or more ideally, an asset imageCollection
exportPathRoot = 'users/ianhousman/test'

#8. Choose medoid or median compositing method. 
#Median tends to be smoother, while medoid retains 
#single date of observation across all bands
#If not exporting indices with composites to save space, medoid should be used
compositingMethod = 'median'

#MODIS Params- params if sensorProgram is modis
#Whether to use daily MODIS (true) or 8 day composites (false)
#Daily images provide complete control of cloud/cloud shadow masking as well as compositing
#Daily images have a shorter lag time as well (~2-4 days) vs pre-computed
#8-day composites (~7 days)
daily = True

#If using daily, the following parameters apply
zenithThresh  = 50#If daily == True, Zenith threshold for daily acquisitions for including observations

despikeMODIS = False#Whether to despike MODIS collection
modisSpikeThresh = 0.1#Threshold for identifying spikes.  Any pair of images that increases and decreases (positive spike) or decreases and increases (negative spike) in a three image series by more than this number will be masked out



# 12. Choose cloud/cloud shadow masking method
# Choices are a series of booleans for cloudScore, TDOM, and QA (if using daily images)
#CloudScore runs pretty quickly, but does look at the time series to find areas that 
#always have a high cloudScore to reduce comission errors- this takes some time
#and needs a longer time series (>5 years or so)
#TDOM also looks at the time series and will need a longer time series
applyCloudScore = True
applyQACloudMask = False#Whether to use QA bits for cloud masking


applyTDOM = False


#13. Cloud and cloud shadow masking parameters.
#If cloudScoreTDOM is chosen
#cloudScoreThresh: If using the cloudScoreTDOMShift method-Threshold for cloud 
#   masking (lower number masks more clouds.  Between 10 and 30 generally 
#   works best)
cloudScoreThresh = 200

#Whether to find if an area typically has a high cloudScore
#If an area is always cloudy, this will result in cloud masking omission
#For bright areas that may always have a high cloudScore
#but not actually be cloudy, this will result in a reduction of commission errors
#This procedure needs at least 5 years of data to work well
performCloudScoreOffset = True

#If performCloudScoreOffset = True:
#Percentile of cloud score to pull from time series to represent a minimum for 
#the cloud score over time for a given pixel. Reduces comission errors over 
#cool bright surfaces. Generally between 5 and 10 works well. 0 generally is a
#bit noisy but may be necessary in persistently cloudy areas
cloudScorePctl = 0

#zScoreThresh: Threshold for cloud shadow masking- lower number masks out 
#   less. Between -0.8 and -1.2 generally works well
zScoreThresh = -1

#shadowSumThresh: Sum of IR bands to include as shadows within TDOM and the 
#   shadow shift method (lower number masks out less)
shadowSumThresh = 0.35

#contractPixels: The radius of the number of pixels to contract (negative 
#   buffer) clouds and cloud shadows by. Intended to eliminate smaller cloud 
#   patches that are likely errors
#(1.5 results in a -1 pixel buffer)(0.5 results in a -0 pixel buffer)
#(1.5 or 2.5 generally is sufficient)
contractPixels = 0

#dilatePixels: The radius of the number of pixels to dilate (buffer) clouds 
#   and cloud shadows by. Intended to include edges of clouds/cloud shadows 
#   that are often missed
#(1.5 results in a 1 pixel buffer)(0.5 results in a 0 pixel buffer)
#(2.5 or 3.5 generally is sufficient)
dilatePixels = 3.5


#Export params
crs = 'EPSG:5070'
transform = [250,0,-2361915.0,0,-250,3177735.0]#Specify transform if scale is None and snapping to known grid is needed
scale = None#Specify scale if transform is None
#########################################################################
#End user parameters
#########################################################################
#########################################################################
#########################################################################
#Start function calls
#Prepare dates
#Wrap the dates if needed
if startJulian > endJulian:
  endJulian = endJulian + 365

startDate = ee.Date.fromYMD(startYear,1,1).advance(startJulian-1,'day')
endDate = ee.Date.fromYMD(endYear,1,1).advance(endJulian-1,'day')
# print('Start and end dates:', startDate.getInfo(), endDate.getInfo())

if applyCloudScore:
  useTempInCloudMask = True
else:
  useTempInCloudMask = False#Whether to use the temperature band in cloud masking- necessary to use temp in bright arid areas

#########################################################################
#Get MODIS image collection
modisImages = getModisData(startYear,endYear,startJulian,endJulian,daily,applyQACloudMask,zenithThresh,useTempInCloudMask)

# Map.addLayer(ee.Image(modisImages.first()),vizParamsFalse,'original',True)

Map.addLayer(ee.Image(modisImages.first()).reproject(crs,transform),vizParamsFalse,'Before Masking',False);

  

#Apply relevant cloud masking methods
if applyCloudScore:
  print('Applying cloudScore');
  cs = modisCloudScore(ee.Image(modisImages.first()))
  # modisImages = applyCloudScoreAlgorithm(modisImages,modisCloudScore,cloudScoreThresh,cloudScorePctl,contractPixels,dilatePixels,performCloudScoreOffset) 
  Map.addLayer(cs,{'min':0,'max':100},'cloudscore')
  # Map.addLayer(ee.Image(modisImages.first()).reproject(crs,transform),vizParamsFalse,'After cloud Masking',False);


# // Map.addLayer(modisImages.min(),getImageLib.vizParamsFalse,'beforetdom') 

# if(applyTDOM){
#   print('Applying TDOM');
#   // Find and mask out dark outliers
#   modisImages = getImageLib.simpleTDOM2(modisImages,zScoreThresh,shadowSumThresh,contractPixels,dilatePixels);
# // Map.addLayer(modisImages.min(),getImageLib.vizParamsFalse,'aftertdom') 
# }

# if(despikeMODIS){
#     print('Despiking MODIS');
#     modisImages = getImageLib.despikeCollection(modisImages,modisSpikeThresh,'nir');
   
  
# }

# Map.addLayer(modisImages.median(),{min:0.05,max:0.7,bands:'swir1,nir,red'},'After Masking',false) 



# // // Add zenith and azimuth
# // if (correctIllumination){
# //   ls = ls.map(function(img){
# //     return getImageLib.addZenithAzimuth(img,toaOrSR);
# //   });
# // }

# // Add common indices- can use addIndices for comprehensive indices 
# //or simpleAddIndices for only common indices
# modisImages = modisImages.map(getImageLib.simpleAddIndices);

# // Create composite time series
# var modisImages = getImageLib.compositeTimeSeries(modisImages,startYear,endYear,startJulian,endJulian,timebuffer,weights,compositingMethod,null);
# var f = ee.Image(modisImages.first());
# Map.addLayer(f,getImageLib.vizParamsFalse,'First-non-illuminated',false);

# // // Correct illumination
# // if (correctIllumination){
# //   print('Correcting illumination');
# //   ts = ts.map(getImageLib.illuminationCondition)
# //     .map(function(img){
# //       return getImageLib.illuminationCorrection(img, correctScale,studyArea);
# //     });
# //   var f = ee.Image(ts.first());
# //   Map.addLayer(f,getImageLib.vizParamsFalse,'First-illuminated',false);
# // }


# // Export composite collection
# var exportBands = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2'];
# getImageLib.exportCollection(exportPathRoot,outputName,studyArea, crs,transform,scale,
# modisImages,startYear,endYear,startJulian,endJulian,null,timebuffer,exportBands);

# // /////////////////////////////////////////////////////////////////////////////////////////////

# // ///////////////////////////////////////
# // // Create composite time series
# // var mts = getImageLib.compositeTimeSeries(modis,startYear,endYear,startJulian,endJulian,timebuffer,weights,compositingMethod);
# // var first = ee.Image(mts.first());
# // Map.addLayer(first,getImageLib.vizParamsFalse,'modis')
# // // ////////////////////////////////////////////////////////////////////////////////
# // // Load the study region, with a blue outline.
# // // Create an empty image into which to paint the features, cast to byte.
# // // Paint all the polygon edges with the same number and width, display.
# // var empty = ee.Image().byte();
# // var outline = empty.paint({
# //   featureCollection: studyArea,
# //   color: 1,
# //   width: 3
# // });
# // Map.addLayer(outline, {palette: '0000FF'}, "Study Area", false);
# // // Map.centerObject(studyArea, 6);
Map.launchGEEVisualization()