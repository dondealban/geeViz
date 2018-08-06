///////////////////////////////////////////////

// var tcc = ee.Image('USGS/NLCD/NLCD2011').select([0])
// Map.addLayer(tcc,{},'tcc')

//########################################################################################################

//########################################################################################################
//##### UNPACKING LT-GEE OUTPUT STRUCTURE FUNCTIONS ##### 
//########################################################################################################

// ----- FUNCTION TO EXTRACT VERTICES FROM LT RESULTS AND STACK BANDS -----
var getLTvertStack = function(LTresult) {
  var emptyArray = [];                              // make empty array to hold another array whose length will vary depending on maxSegments parameter    
  var vertLabels = [];                              // make empty array to hold band names whose length will vary depending on maxSegments parameter 
  var iString;                                      // initialize variable to hold vertex number
  for(var i=1;i<=run_params.maxSegments+1;i++){     // loop through the maximum number of vertices in segmentation and fill empty arrays
    iString = i.toString();                         // define vertex number as string 
    vertLabels.push("vert_"+iString);               // make a band name for given vertex
    emptyArray.push(0);                             // fill in emptyArray
  }
  
  var zeros = ee.Image(ee.Array([emptyArray,        // make an image to fill holes in result 'LandTrendr' array where vertices found is not equal to maxSegments parameter plus 1
                                 emptyArray,
                                 emptyArray]));
  
  var lbls = [['yrs_','src_','fit_'], vertLabels,]; // labels for 2 dimensions of the array that will be cast to each other in the final step of creating the vertice output 

  var vmask = LTresult.arraySlice(0,3,4);           // slices out the 4th row of a 4 row x N col (N = number of years in annual stack) matrix, which identifies vertices - contains only 0s and 1s, where 1 is a vertex (referring to spectral-temporal segmentation) year and 0 is not
  
  var ltVertStack = LTresult.arrayMask(vmask)       // uses the sliced out isVert row as a mask to only include vertice in this data - after this a pixel will only contain as many "bands" are there are vertices for that pixel - min of 2 to max of 7. 
                      .arraySlice(0, 0, 3)          // ...from the vertOnly data subset slice out the vert year row, raw spectral row, and fitted spectral row
                      .addBands(zeros)              // ...adds the 3 row x 7 col 'zeros' matrix as a band to the vertOnly array - this is an intermediate step to the goal of filling in the vertOnly data so that there are 7 vertice slots represented in the data - right now there is a mix of lengths from 2 to 7
                      .toArray(1)                   // ...concatenates the 3 row x 7 col 'zeros' matrix band to the vertOnly data so that there are at least 7 vertice slots represented - in most cases there are now > 7 slots filled but those will be truncated in the next step
                      .arraySlice(1, 0, run_params.maxSegments+1) // ...before this line runs the array has 3 rows and between 9 and 14 cols depending on how many vertices were found during segmentation for a given pixel. this step truncates the cols at 7 (the max verts allowed) so we are left with a 3 row X 7 col array
                      .arrayFlatten(lbls, '');      // ...this takes the 2-d array and makes it 1-d by stacking the unique sets of rows and cols into bands. there will be 7 bands (vertices) for vertYear, followed by 7 bands (vertices) for rawVert, followed by 7 bands (vertices) for fittedVert, according to the 'lbls' list

  return ltVertStack;                               // return the stack
};





//########################################################################################################
//##### GREATEST DISTURBANCE EXTRACTION FUNCTIONS #####
//########################################################################################################

// ----- function to extract greatest disturbance based on spectral delta between vertices 
var extractDisturbance = function(lt, distDir, params, mmu) {
  // select only the vertices that represents a change
  var vertexMask = lt.arraySlice(0, 3, 4); // get the vertex - yes(1)/no(0) dimension
  var vertices = lt.arrayMask(vertexMask); // convert the 0's to masked
  
  // construct segment start and end point years and index values
  var left = vertices.arraySlice(1, 0, -1);    // slice out the vertices as the start of segments
  var right = vertices.arraySlice(1, 1, null); // slice out the vertices as the end of segments
  var startYear = left.arraySlice(0, 0, 1);    // get year dimension of LT data from the segment start vertices
  var startVal = left.arraySlice(0, 2, 3);     // get spectral index dimension of LT data from the segment start vertices
  var endYear = right.arraySlice(0, 0, 1);     // get year dimension of LT data from the segment end vertices 
  var endVal = right.arraySlice(0, 2, 3);      // get spectral index dimension of LT data from the segment end vertices
  
  var dur = endYear.subtract(startYear);       // subtract the segment start year from the segment end year to calculate the duration of segments 
  var mag = endVal.subtract(startVal);         // substract the segment start index value from the segment end index value to calculate the delta of segments 

  // concatenate segment start year, delta, duration, and starting spectral index value to an array 
  var distImg = ee.Image.cat([startYear.add(1), mag, dur, startVal.multiply(distDir)]).toArray(0); // make an image of segment attributes - multiply by the distDir parameter to re-orient the spectral index if it was flipped for segmentation - do it here so that the subtraction to calculate segment delta in the above line is consistent - add 1 to the detection year, because the vertex year is not the first year that change is detected, it is the following year
 
  // sort the segments in the disturbance attribute image delta by spectral index change delta  
  var distImgSorted = distImg.arraySort(mag.multiply(-1));                                  // flip the delta around so that the greatest delta segment is first in order

  // slice out the first (greatest) delta
  var tempDistImg = distImgSorted.arraySlice(1, 0, 1).unmask(ee.Image(ee.Array([[0],[0],[0],[0]])));                                      // get the first segment in the sorted array

  // make an image from the array of attributes for the greatest disturbance
  var finalDistImg = ee.Image.cat(tempDistImg.arraySlice(0,0,1).arrayProject([1]).arrayFlatten([['yod']]),     // slice out year of disturbance detection and re-arrange to an image band 
                                  tempDistImg.arraySlice(0,1,2).arrayProject([1]).arrayFlatten([['mag']]),     // slice out the disturbance magnitude and re-arrange to an image band 
                                  tempDistImg.arraySlice(0,2,3).arrayProject([1]).arrayFlatten([['dur']]),     // slice out the disturbance duration and re-arrange to an image band
                                  tempDistImg.arraySlice(0,3,4).arrayProject([1]).arrayFlatten([['preval']])); // slice out the pre-disturbance spectral value and re-arrange to an image band
  
  // filter out disturbances based on user settings
  var threshold = ee.Image(finalDistImg.select(['dur']))                        // get the disturbance band out to apply duration dynamic disturbance magnitude threshold 
                    .multiply((params.tree_loss20 - params.tree_loss1) / 19.0)  // ...
                    .add(params.tree_loss1)                                     //    ...interpolate the magnitude threshold over years between a 1-year mag thresh and a 20-year mag thresh
                    .lte(finalDistImg.select(['mag']))                          // ...is disturbance less then equal to the interpolated, duration dynamic disturbance magnitude threshold 
                    .and(finalDistImg.select(['mag']).gt(0))                    // and is greater than 0  
                    .and(finalDistImg.select(['preval']).gt(params.pre_val));   // and is greater than pre-disturbance spectral index value threshold
  
  // apply the filter mask
  finalDistImg = finalDistImg.mask(threshold).int16(); 
  
   // patchify the remaining disturbance pixels using a minimum mapping unit
  if(mmu > 1){
    var mmuPatches = finalDistImg.select(['yod'])           // patchify based on disturbances having the same year of detection
                            .connectedPixelCount(mmu, true) // count the number of pixel in a candidate patch
                            .gte(mmu);                      // are the the number of pixels per candidate patch greater than user-defined minimum mapping unit?
    finalDistImg = finalDistImg.updateMask(mmuPatches);     // mask the pixels/patches that are less than minimum mapping unit
  } 
  
  return finalDistImg; // return the filtered greatest disturbance attribute image
};
//////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////

