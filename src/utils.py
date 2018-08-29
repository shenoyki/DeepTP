# -*- coding: utf-8 -*-
# @Author: liuyulin
# @Date:   2018-08-16 14:51:38
# @Last Modified by:   liuyulin
# @Last Modified time: 2018-08-28 18:27:42

# api functions that are mostly called by other paks

# Trajectory dimension reduction algo.
import numpy as np
import pandas as pd
from pyproj import Geod
from dateutil import parser

global baseline_time
baseline_time = parser.parse('01/01/2013 0:0:0')
g=Geod(ellps='WGS84')
# reference:
# http://hanj.cs.illinois.edu/pdf/sigmod07_jglee.pdf
# Lee, Han and Whang (2007) trajectory clustering a partition-and-group framework


### Legacy code
### legacy code usually has non-pythonic naming convention
def GetAzimuth(flight_track_df, 
               last_pnt = 0.0):
    # return azimuth in degrees
    CenterTraj = flight_track_df[['FID', 'Lat', 'Lon']]
    CenterTraj['azimuth'] = last_pnt
    tmp_df = CenterTraj.shift(-1)

    azimuth_arr = g.inv(CenterTraj.Lon.values[:-1], 
                        CenterTraj.Lat.values[:-1], 
                        tmp_df.Lon.values[:-1], 
                        tmp_df.Lat.values[:-1])[0]

    CenterTraj.iloc[:-1]['azimuth'] = azimuth_arr
    CenterTraj.loc[CenterTraj.groupby("FID")['azimuth'].tail(1).index, 'azimuth'] = last_pnt
    return CenterTraj.azimuth

def ReshapeTrajLine(Traj):
    RepeatIndex = np.ones(Traj.shape[0],dtype=int)*2
    RepeatIndex[0] = 1
    RepeatIndex[-1] = 1
    NewTraj = np.repeat(Traj,RepeatIndex,axis = 0)
    NewTraj = NewTraj.reshape(Traj.shape[0]-1,Traj.shape[1]*2)
    return NewTraj

#################################################################################
#################################################################################

def LineDist(Si,Ei,Sj,Ej,Out = 'All'):
    """
    Get line segment distance between SjEj and SiEi
    Input must be numpy array
    Line segment 1: SiEi
    Line segment 2: SjEj
    Project Line SjEj to SiEi
    
    test code
    LineDist(np.array([0,1]),np.array([1,1]),np.array([0,0]),np.array([1,0]))
    """
    SiEi = Ei - Si
    SjEj = Ej - Sj
    
    SiSj = Sj - Si
    SiEj = Ej - Si
    
    u1 = np.dot(SiSj, SiEi)/np.dot(SiEi,SiEi)
    u2 = np.dot(SiEj, SiEi)/np.dot(SiEi,SiEi)
    
    Ps = Si + np.dot(u1,SiEi)
    Pe = Si + np.dot(u2,SiEi)
    
    CosTheta = np.dot(SiEi,SjEj)/np.sqrt(np.dot(SiEi,SiEi))/np.sqrt(np.dot(SjEj,SjEj))   
    
    L_perp1 = np.sqrt(np.dot(Sj-Ps,Sj-Ps))
    L_perp2 = np.sqrt(np.dot(Ej-Pe,Ej-Pe))
    
    if L_perp1 + L_perp2 == 0:
        D_perp = 0
    else:
        D_perp = (L_perp1**2 + L_perp2**2)/(L_perp1+L_perp2)
    
    L_para1 = min(np.dot(Ps-Si,Ps-Si),np.dot(Ps-Ei,Ps-Ei))
    L_para2 = min(np.dot(Ei-Pe,Ei-Pe),np.dot(Si-Pe,Si-Pe))
    D_para = np.sqrt(min(L_para1,L_para2))
    
    if CosTheta >= 0 and CosTheta < 1:
        D_theta = np.sqrt(np.dot(SjEj,SjEj)) * np.sqrt(1-CosTheta**2)
    elif CosTheta < 0:
        D_theta = np.sqrt(np.dot(SjEj,SjEj))
    else:
        D_theta = 0
    
    D_line = D_perp + D_para + D_theta    
    
    if Out == 'All':
        return D_perp, D_para, D_theta, D_line
    elif Out == 'Total':
        return D_line
    elif Out == 'Nopara':
        return D_perp + D_theta
    else:
        raise ValueError('Out can only be All, Total or Nopara')

def MDL_PAR(Traj, m, n, dist = lambda a, b: np.sqrt(sum((a - b)**2))):
    LH  = (dist(Traj[m],Traj[n]))
    LD = 0
    for i in range(m,n):
        DD = LineDist(Traj[m],Traj[n],Traj[i],Traj[i+1])
        LD += np.log2(DD[0] + 1) + np.log2(DD[2] + 1)
    LL = np.log2(LH + 1) + LD
    return LL

def MDL_NOPAR(Traj, m, n, dist = lambda a, b: np.sqrt(sum((a - b)**2))):
    LD = 0
    LH = 0
    for i in range(m,n):
        LH += (dist(Traj[i],Traj[i+1]))

    LL = np.log2(LH + 1) + np.log2(LD + 1)
    return LL

def GetCharaPnt(Traj,alpha, dist = lambda a, b: np.sqrt(sum((a - b)**2))):
    """
    Get Characteristic points
    
    # test code
    Traj = np.random.random((300,2))
    aa = time.time()
    CP = GetCharaPnt(Traj,1.5)
    print(time.time() - aa)
    print(len(CP))
    """
    startIndex = 1
    Length = 1
    CP = [Traj[0]]
    while startIndex + Length < Traj.shape[0]:
        currIndex = startIndex + Length
        cost_par = MDL_PAR(Traj, startIndex, currIndex, dist)
        cost_nopar = MDL_NOPAR(Traj, startIndex, currIndex, dist)
        # print(currIndex, startIndex, Length, cost_par, cost_nopar)
        if cost_par > cost_nopar * alpha:
            startIndex = currIndex - 1
            Length = 1
            CP.append(Traj[startIndex])
        else:
            Length += 1
    CP.append(Traj[-1])
    return np.array(CP)

#################################################################################
#################################################################################

def downsample_track_data(path_to_fp,
                          path_to_fp_util,
                          path_to_track,
                          downsamp_rate_ft = 2,
                          downsamp_rate_fp = 1.05):
    """
    use case:
    downsamp_flight_tracks, \
        downsamp_flight_plans, 
            flight_plans, \
                flight_plans_util, \
                    flight_tracks = preprocess_track_data(path_to_fp = '/media/storage/DATA/DeepTPdata/cleaned_FP_tracks.CSV',
                                                                       path_to_fp_util = '/media/storage/DATA/DeepTPdata/IAH_BOS_Act_Flt_Trk_20130101_1231.CSV',
                                                                       path_to_track = '/media/storage/DATA/DeepTPdata/New_IAHBOS2013.csv',
                                                                       downsamp_rate_ft = 2,
                                                                       downsamp_rate_fp = 1.05)
    """
    flight_plans = pd.read_csv(path_to_fp)
    flight_plans_util = pd.read_csv(path_to_fp_util)
    flight_tracks = pd.read_csv(path_to_track, parse_dates=[6])
    tmp_ft_head = flight_tracks.groupby('FID').head(1)
    tmp_ft_tail = flight_tracks.groupby('FID').tail(1)
    tmp_ft = flight_tracks.loc[flight_tracks.index.difference(tmp_ft_head.index)[::downsamp_rate_ft]]
    downsamp_flight_tracks = pd.concat([tmp_ft_head, tmp_ft_tail, tmp_ft])
#     del tmp_ft
#     del tmp_ft_head
#     del tmp_ft_tail
    downsamp_flight_tracks.sort_index(inplace=True)
    downsamp_flight_tracks = downsamp_flight_tracks.reset_index(drop = True)
    downsamp_flight_tracks['DT'] = downsamp_flight_tracks.groupby('FID')['Elap_Time'].apply(lambda x: (x - x.shift(1)).dt.seconds)
    downsamp_flight_tracks['DT'] = downsamp_flight_tracks['DT'].fillna(0)
    
    downsamp_flight_plans = []
    for gpidx, gp in flight_plans.groupby('FLT_PLAN_ID'):
        tmp_fp_cp = GetCharaPnt(gp[['LONGITUDE', 'LATITUDE']].values, alpha=downsamp_rate_fp,dist = lambda a, b: g.inv(a[0], a[1], b[0], b[1])[2]/1000)
        tmp_fp_cp = pd.DataFrame(data = tmp_fp_cp, columns=['LONGITUDE', 'LATITUDE'])
        tmp_fp_cp['FLT_PLAN_ID'] = gpidx
        downsamp_flight_plans.append(tmp_fp_cp)
    downsamp_flight_plans = pd.concat(downsamp_flight_plans).reset_index(drop = True)
    return downsamp_flight_tracks, downsamp_flight_plans, flight_plans, flight_plans_util, flight_tracks

#################################################################################
#################################################################################

def rotate_coord(old_coord, theta):
    rotation_matrix = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    new_coord = rotation_matrix.dot(old_coord)
    return new_coord
    
def create_grid(center_x, center_y, shift_xleft, shift_xright, shift_yup, shift_ydown, nx, ny, theta):
    """
    rotate_grid = create_grid(center_x = -95, 
                        center_y = 30, 
                        shift_xleft = 0, 
                        shift_xright = 2, 
                        shift_yup = 1, 
                        shift_ydown = 1, 
                        nx = 10, 
                        ny = 10, 
                        theta = np.pi/4)
    """
    # x, y is in the unit of degrees
    x = np.linspace(0 - shift_xleft, 0 + shift_xright, nx)
    y = np.linspace(0 - shift_ydown, 0 + shift_yup, ny)
    xv, yv = np.meshgrid(x, y, sparse = False)
    grid_2d = np.vstack((xv.flatten(),yv.flatten()))
    rotate_grid = rotate_coord(grid_2d, theta).T + np.array([[center_x, center_y]])
    # [Lon, Lat]
    return rotate_grid



def plot_fp_act(FP_ID, IAH_BOS_FP_utilize, IAH_BOS_ACT_track, IAH_BOS_FP_track):
    import matplotlib.pyplot as plt
    from mpl_toolkits.basemap import Basemap
    """
    test code:
    _, _ = plot_fp_act('FP_00001', flight_plans_util, downsamp_flight_tracks, downsamp_flight_plans)
    """
    fig = plt.figure(figsize=(8,6))
    m = Basemap(llcrnrlon = -100,llcrnrlat = 27,urcrnrlon = -68,urcrnrlat = 46,projection='merc')
    m.bluemarble()
    m.drawcoastlines(linewidth=0.5)
    m.drawcountries(linewidth=0.5)
    m.drawstates(linewidth=0.5)
    m.drawparallels(np.arange(10.,35.,5.))
    m.drawmeridians(np.arange(-120.,-80.,10.))

    fid_fp1 = IAH_BOS_FP_utilize.loc[IAH_BOS_FP_utilize.FLT_PLAN_ID == FP_ID, 'FID'].values
    print('%d flights filed flight plan %s'%(fid_fp1.shape[0], FP_ID))
    plot_track = IAH_BOS_ACT_track.loc[IAH_BOS_ACT_track.FID.isin(fid_fp1)]
    plot_fp = IAH_BOS_FP_track.loc[IAH_BOS_FP_track.FLT_PLAN_ID == FP_ID]
    x_fp, y_fp = m(plot_fp.LONGITUDE.values, plot_fp.LATITUDE.values)

    for gpidx, gp in plot_track.groupby('FID'):
        x,y = m(gp.Lon.values, gp.Lat.values)
        actual, = plt.plot(x,y,'-o', linewidth = 0.1, ms = 1, color='y', label = 'Actual Tracks')
    fp, = plt.plot(x_fp, y_fp, '-o', linewidth = 2, ms = 5, color='r', label = 'Flight Plans', zorder = 999)
    plt.show()
    return plot_track, plot_fp