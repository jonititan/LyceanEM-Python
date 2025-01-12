#!/usr/bin/env python
# coding: utf-8
"""
Modelling Different Farfield Polarisations
======================================================

This example uses the frequency domain :func:`lyceanem.models.frequency_domain.calculate_farfield` function to predict
the farfield pattern for a linearly polarised aperture. This could represent an antenna array without any beamforming
weights.


"""
import numpy as np
import open3d as o3d
import copy

# %%
# Setting Farfield Resolution and Wavelength
# -------------------------------------------
# LyceanEM uses Elevation and Azimuth to record spherical coordinates, ranging from -180 to 180 degrees in azimuth,
# and from -90 to 90 degrees in elevation. In order to launch the aperture projection function, the resolution in
# both azimuth and elevation is requried.
# In order to ensure a fast example, 37 points have been used here for both, giving a total of 1369 farfield points.
#
# The wavelength of interest is also an important variable for antenna array analysis, so we set it now for 10GHz,
# an X band aperture.

az_res = 37
elev_res = 37
wavelength = 3e8 / 10e9

# %%
# Generating consistent Horn Antenna and
# -------------------------------------------

import lyceanem.geometry.targets as TL
from lyceanem.base_classes import points,structures,antenna_structures

#horn_body, aperture_coords = TL.meshedHorn(
#    58e-3, 58e-3, 128e-3, 2e-3, 0.21, 0.5*wavelength
#)
aperture_coords=o3d.geometry.PointCloud()
point1=np.asarray([0.0,0,0]).reshape(1,3)
normal1=np.asarray([0,0,1.0]).reshape(1,3)
aperture_coords.points=o3d.utility.Vector3dVector(point1)
aperture_coords.normals=o3d.utility.Vector3dVector(normal1)
aperture=points([aperture_coords])
blockers=structures([None])
point_antenna=antenna_structures(blockers, aperture)


desired_E_axis = np.zeros((1, 3), dtype=np.complex64)
desired_E_axis[0, 0] = 1.0
u_pattern=point_antenna.generate_farfield(desired_E_axis, wavelength)
u_pattern.display_pattern(desired_pattern='Power')


desired_E_axis = np.zeros((1, 3), dtype=np.complex64)
desired_E_axis[0, 1] = 1.0
v_pattern=point_antenna.generate_farfield(desired_E_axis, wavelength)
v_pattern.display_pattern(desired_pattern='Power')


desired_E_axis = np.zeros((1, 3), dtype=np.complex64)
desired_E_axis[0, 2] = 1.0
n_pattern=point_antenna.generate_farfield(desired_E_axis, wavelength)
n_pattern.display_pattern(desired_pattern='Power')

point_antenna.rotate_antenna(o3d.geometry.get_rotation_matrix_from_axis_angle(np.radians(np.asarray([0.0,0.0,90.0]))))

desired_E_axis = np.zeros((1, 3), dtype=np.complex64)
desired_E_axis[0, 0] = 1.0
u_pattern=point_antenna.generate_farfield(desired_E_axis, wavelength)
u_pattern.display_pattern(desired_pattern='Power')


desired_E_axis = np.zeros((1, 3), dtype=np.complex64)
desired_E_axis[0, 1] = 1.0
v_pattern=point_antenna.generate_farfield(desired_E_axis, wavelength)
v_pattern.display_pattern(desired_pattern='Power')


desired_E_axis = np.zeros((1, 3), dtype=np.complex64)
desired_E_axis[0, 2] = 1.0
n_pattern=point_antenna.generate_farfield(desired_E_axis, wavelength)
n_pattern.display_pattern(desired_pattern='Power')