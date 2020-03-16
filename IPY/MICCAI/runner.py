import os, time
import numpy as np
import nibabel as nib
import pickle
import trako as TKO
import vtk
import getpass

class Runner:

  @staticmethod
  def vtk2streamlines(number_of_streamlines, lines, points):

    streamlines = []

    i = 0
    line_index = 0
    line_length = lines[i]
    ordered_indices = []

    while (line_index<number_of_streamlines):

      current_line = lines[i+1+line_index:i+1+line_length+line_index]
      
      streamlines.append(points[current_line])
      i += line_length
      line_index += 1
      if line_index < number_of_streamlines:
        line_length = lines[i+line_index]

    return streamlines

  @staticmethod
  def error_per_streamlines(streamlines1, streamlines2):
    '''
    '''
    min_e = []
    max_e = []
    mean_e = []
    std_e = []

    end_min_e = []
    end_max_e = []
    end_mean_e = []
    end_std_e = []
    for i,s in enumerate(streamlines1):
      s1 = s
      s2 = streamlines2[i]
      error, end_error = Runner.error_per_fiber(s1, s2)
      min_e.append(error[0])
      max_e.append(error[1])
      mean_e.append(error[2])
      std_e.append(error[3])
      end_min_e.append(end_error[0])
      end_max_e.append(end_error[1])
      end_mean_e.append(end_error[2])
      end_std_e.append(end_error[3])

    min_e = np.min(min_e)
    max_e = np.max(max_e)
    mean_e = np.mean(mean_e)
    std_e = np.mean(std_e)

    end_min_e = np.min(end_min_e)
    end_max_e = np.max(end_max_e)
    end_mean_e = np.mean(end_mean_e)
    end_std_e = np.mean(end_std_e)

    return (min_e, max_e, mean_e, std_e), (end_min_e, end_max_e, end_mean_e, end_std_e)


  @staticmethod
  def error_per_fiber(points1, points2):
    '''
    Same as TKO UTIL but for xyz
    '''

    error = []

    for i,p in enumerate(points1):

      p1 = points1[i]
      p2 = points2[i]

      dist = np.linalg.norm(p1-p2)

      error.append(dist)

    error = (np.min(error), np.max(error), np.mean(error), np.std(error))
    end_error = [np.linalg.norm(points1[0]-points2[0]), np.linalg.norm(points1[-1]-points2[-1])]
    end_error = (np.min(end_error), np.max(end_error), np.mean(end_error), np.std(end_error))

    return error, end_error


  @staticmethod
  def sizestats(original, compressed):
    '''
    '''
    originalsize = os.path.getsize(original)
    compressedsize = os.path.getsize(compressed)

    c_ratio = (1-float(compressedsize)/float(originalsize))*100
    c_factor = float(originalsize) / float(compressedsize)

    return (originalsize, compressedsize, c_ratio, c_factor)


  @staticmethod
  def tko(workingdir, input, compressed=None, restored=None, config=None, force=False, coords_only=False, verbose=False):
    '''
    '''

    if not input.endswith('vtp') and not input.endswith('vtk'):
      # we need to convert
      print('Invalid format')
      return None

    configstr = ''
    if config:
      configstr = '_config'+config['name']

    if not compressed:
      compressed = input + '_compressed'+str(configstr)+'.tko'

    if not restored:
      restored = input + '_restored'+str(configstr)+'.vtp'

    original = os.path.join(workingdir, input)

    #
    # compression
    #
    c_time = -1
    if not os.path.exists(os.path.join(workingdir, compressed)) or force:
      # compress again!
      t0 = time.time()
      tko = TKO.Encoder.fromVtp(original, config=config, verbose=False, coords_only=coords_only)
      tko.save(os.path.join(workingdir, compressed))
      c_time = time.time()-t0

      if verbose:
        print('compression done.')

    #
    # restoring
    #
    d_time = -1
    if not os.path.exists(os.path.join(workingdir, restored)) or force:
      # restore again!
      t0 = time.time()
      restored_polydata = TKO.Decoder.toVtp(os.path.join(workingdir, compressed), verbose=False)

      w = vtk.vtkXMLPolyDataWriter()
      w.SetFileName(os.path.join(workingdir, restored))
      w.SetInputData(restored_polydata)
      w.Update()
      d_time = time.time()-t0

      if verbose:
        print('restoring done.')


    #
    # calculate errors
    #
    stats = compressed + '_stats'+str(configstr)+'.p'
    if not os.path.exists(os.path.join(workingdir, stats)) or force:

      original_data = TKO.Util.loadvtp(original)

      original_streamlines = Runner.vtk2streamlines(original_data['number_of_streamlines'], 
                                                    original_data['lines'], 
                                                    original_data['points'])

      restored_data = TKO.Util.loadvtp(os.path.join(workingdir, restored))

      restored_streamlines = Runner.vtk2streamlines(restored_data['number_of_streamlines'], 
                                                    restored_data['lines'], 
                                                    restored_data['points'])

      statsdata = Runner.error_per_streamlines(original_streamlines, restored_streamlines)
      sizestatsdata = Runner.sizestats(os.path.join(workingdir, original), os.path.join(workingdir, compressed))

      statsdata = [c_time, d_time, sizestatsdata, statsdata[0], statsdata[1]]

      with open(os.path.join(workingdir, stats), 'wb') as f:
        pickle.dump(statsdata, f)

    else:
      with open(os.path.join(workingdir, stats), 'rb') as f:
        statsdata = pickle.load(f)

    [c_time, d_time, sizestatsdata, (min_e, max_e, mean_e, std_e), (end_min_e, end_max_e, end_mean_e, end_std_e)] = \
      statsdata

    if verbose:
      print('Times', c_time, d_time)
      print('Size Stats', sizestatsdata)
      print('Error', min_e, max_e, mean_e, std_e)
      print('Endpoint Error', end_min_e, end_max_e, end_mean_e, end_std_e)

    return statsdata



  @staticmethod
  def qfib(workingdir, input, compressed=None, restored=None, bits=8, force=False, verbose=False):
    '''
    '''

    QFIB = '/home/'+getpass.getuser()+'/Projects/qfib/qfib'

    if not input.endswith('tck'):
      # we need to convert
      print('Invalid format')
      return None


    if not compressed:
      compressed = input + '_compressed'+str(bits)+'.qfib'

    if not restored:
      restored = input + '_restored'+str(bits)+'.tck'

    original = os.path.join(workingdir, input)

    #
    # compression
    #
    bitflag = ''
    if bits==16:
      bitflag = ' -b'
    c_time = -1
    if not os.path.exists(os.path.join(workingdir, compressed)) or force:
      # compress again!
      logfile = os.path.join(workingdir, compressed+'.log')
      t0 = time.time()
      cmd = QFIB+' '+original+' '+compressed+' -d -c -e -n'+bitflag+' > '+logfile
      os.system('cd '+workingdir+'; '+cmd)
      c_time = time.time()-t0

      if verbose:
        print('compression done.')

    #
    # restoring
    #
    d_time = -1
    if not os.path.exists(os.path.join(workingdir, restored)) or force:
      # restore again!
      t0 = time.time()
      cmd = QFIB+' '+compressed+' '+restored
      os.system('cd '+workingdir+'; '+cmd)
      d_time = time.time()-t0

      if verbose:
        print('restoring done.')


    #
    # calculate errors
    #
    stats = compressed + '_stats'+str(bits)+'.p'
    if not os.path.exists(os.path.join(workingdir, stats)) or force:
      original_data = nib.streamlines.load(os.path.join(workingdir, original), lazy_load=False)
      original_streamlines = original_data.streamlines
      restored_data = nib.streamlines.load(os.path.join(workingdir, restored), lazy_load=False)
      restored_streamlines = restored_data.streamlines

      statsdata = Runner.error_per_streamlines(original_streamlines, restored_streamlines)
      sizestatsdata = Runner.sizestats(os.path.join(workingdir, original), os.path.join(workingdir, compressed))

      statsdata = [c_time, d_time, sizestatsdata, statsdata[0], statsdata[1]]

      with open(os.path.join(workingdir, stats), 'wb') as f:
        pickle.dump(statsdata, f)

    else:
      with open(os.path.join(workingdir, stats), 'rb') as f:
        statsdata = pickle.load(f)


    [c_time, d_time, sizestatsdata, (min_e, max_e, mean_e, std_e), (end_min_e, end_max_e, end_mean_e, end_std_e)] = \
      statsdata

    if verbose:
      print('Times', c_time, d_time)
      print('Size Stats', sizestatsdata)
      print('Error', min_e, max_e, mean_e, std_e)
      print('Endpoint Error', end_min_e, end_max_e, end_mean_e, end_std_e)

    return statsdata
