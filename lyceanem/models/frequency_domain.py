import numpy as np
import open3d as o3d

from ..base import scattering_t, calc_dv_norm
from ..electromagnetics import empropagation as EM
from ..geometry import geometryfunctions as GF
from ..geometry import targets as TL
from ..raycasting import rayfunctions as RF


def aperture_projection(aperture,
                        environment=None,
                        wavelength=1.0,
                        az_range=np.linspace(-180.0, 180.0, 19),
                        elev_range=np.linspace(-90.0, 90.0, 19)):
    """
    Using the aperture provided and any blocking structures, predict the maximum directivity envelope of the aperture.
    This will initially just cover all the triangles of a provided solid, but eventually I will include a filter list.
    """
    if environment is None:
        blocking_triangles=RF.convertTriangles(aperture)
    else:
        blocking_triangles=np.append(RF.convertTriangles(aperture),RF.convertTriangles(environment),axis=0)

    directivity_envelope = np.zeros((elev_range.shape[0], az_range.shape[0]), dtype=np.float32)
    triangle_centroids,_ = GF.tri_centroids(aperture)
    triangle_areas = GF.tri_areas(aperture)
    triangle_normals = np.asarray(aperture.triangle_normals)
    visible_patterns, pcd = RF.visiblespace(triangle_centroids,
                                          triangle_normals,
                                          blocking_triangles,
                                          vertex_area=triangle_areas,
                                          az_range=az_range,
                                          elev_range=elev_range)
    directivity_envelope[:,:] = (4 * np.pi * visible_patterns) / (wavelength ** 2)

    return directivity_envelope,pcd


def calculate_farfield(aperture_coords,
                       antenna_solid,
                       desired_E_axis,
                       az_range,
                       el_range,
                       scatter_points=None,
                       wavelength=1.0,
                       farfield_distance=2.0,
                       scattering=0,
                       scattering_weight=1.0,
                       mesh_resolution=0.5,
                       elements=False,
                       project_vectors=False):
    """
    Based upon the aperture coordinates and solids, predict the farfield for the antenna.

    Inputs
    aperture_coords : open3d point cloud of the aperture coordinates, from a single point to a
    mesh sampling across and aperture or surface
    antenna_solid : open3d triangle mesh of the platform or blockers in the environment
    desired_E_axis : 1*3 numpy array of the

    az_range,

    el_range

    scatter_points

    wavelength

    farfield_distance,

    scattering

    scattering_weight

    mesh_resolution

    elements

    project_vectors
    """

    # create sink points for the model
    azaz, elel = np.meshgrid(az_range, el_range)
    #assuming the elevation range starts as a negative number and then increases to positive range (-90 to 90), calculate the theta range
    _, theta = np.meshgrid(np.linspace(-180.0, 180.0, az_range.shape[0]), GF.elevationtotheta(el_range))
    sinks = np.zeros((len(np.ravel(azaz)), 3), dtype=np.float32)
    sinks[:, 0], sinks[:, 1], sinks[:, 2] = RF.azeltocart(np.ravel(azaz), np.ravel(elel), farfield_distance)
    sink_normals = np.zeros((len(np.ravel(azaz)), 3), dtype=np.float32)
    origin = np.zeros((len(sinks), 3), dtype=np.float32).ravel()
    lengths = np.zeros((len(np.ravel(azaz)), 1), dtype=np.float32)
    sink_normals, _ = calc_dv_norm(sinks, np.zeros((len(sinks), 3), dtype=np.float32), sink_normals, lengths)
    sink_cloud = RF.points2pointcloud(sinks)
    sink_cloud.normals = o3d.utility.Vector3dVector(sink_normals)
    num_sources = len(np.asarray(aperture_coords.points))
    num_sinks = len(np.asarray(sink_cloud.points))
    if project_vectors:
        conformal_E_vectors = EM.calculate_conformalVectors(desired_E_axis,
                                                            np.asarray(aperture_coords.normals).astype(np.float32))
    else:
        conformal_E_vectors=np.repeat(desired_E_axis.reshape(1,3).astype(np.float32),num_sources,axis=0)

    if scattering == 0:
        # only use the aperture point cloud, no scattering required.
        scatter_points = o3d.geometry.PointCloud()
        unified_model = np.append(np.asarray(aperture_coords.points).astype(np.float32),
                                  np.asarray(sink_cloud.points).astype(np.float32), axis=0)
        unified_normals = np.append(np.asarray(aperture_coords.normals).astype(np.float32),
                                    np.asarray(sink_cloud.normals).astype(np.float32), axis=0)
        unified_weights = np.ones((unified_model.shape[0], 3), dtype=np.complex64)
        unified_weights[0:num_sources,:] = conformal_E_vectors / num_sources  # set total amplitude to 1 for the aperture
        unified_weights[num_sources:num_sources + num_sinks,
        :] = 1 / num_sinks  # set total amplitude to 1 for the aperture
        point_informationv2 = np.empty((len(unified_model)), dtype=scattering_t)
        # set all sources as magnetic current sources, and permittivity and permeability as free space
        point_informationv2[:]['Electric'] = True
        point_informationv2[:]['permittivity'] = 8.8541878176e-12
        point_informationv2[:]['permeability'] = 1.25663706212e-6
        # set position, velocity, normal, and weight of sources
        point_informationv2[0:num_sources]['px'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['py'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['pz'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 2]
        point_informationv2[0:num_sources]['nx'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['ny'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['nz'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 2]
        # set position and velocity of sinks
        point_informationv2[num_sources:(num_sources + num_sinks)]['px'] = sinks[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['py'] = sinks[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['pz'] = sinks[:, 2]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nx'] = sink_normals[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['ny'] = sink_normals[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nz'] = sink_normals[:, 2]

        point_informationv2[:]['ex'] = unified_weights[:, 0]
        point_informationv2[:]['ey'] = unified_weights[:, 1]
        point_informationv2[:]['ez'] = unified_weights[:, 2]
        scatter_mask = np.zeros((point_informationv2.shape[0]), dtype=np.int32)
        scatter_mask[0:num_sources] = 0
        scatter_mask[(num_sources + num_sinks):] = 0

    else:
        # create scatter points on antenna solids based upon a half wavelength square
        if scatter_points is None:
            scatter_points, areas = TL.source_cloud_from_shape(antenna_solid, 1e-6,
                                                               (wavelength * mesh_resolution) ** 2 / 2.0)

        unified_model = np.append(np.append(np.asarray(aperture_coords.points).astype(np.float32),
                                            np.asarray(sink_cloud.points).astype(np.float32), axis=0),
                                  np.asarray(scatter_points.points).astype(np.float32), axis=0)
        unified_normals = np.append(np.append(np.asarray(aperture_coords.normals).astype(np.float32),
                                              np.asarray(sink_cloud.normals).astype(np.float32), axis=0),
                                    np.asarray(scatter_points.normals).astype(np.float32), axis=0)
        unified_weights = np.ones((unified_model.shape[0], 3), dtype=np.complex64)
        unified_weights[0:num_sources,
        :] = conformal_E_vectors / num_sources  # set total amplitude to 1 for the aperture
        unified_weights[num_sources:num_sources + num_sinks,
        :] = 1 / num_sinks  # set total amplitude to 1 for the aperture
        unified_weights[num_sources + num_sinks:,
        :] = scattering_weight #/ len(np.asarray(scatter_points.points))  # set total amplitude to 1 for the aperture
        point_informationv2 = np.empty((len(unified_model)), dtype=scattering_t)
        # set all sources as magnetic current sources, and permittivity and permeability as free space
        point_informationv2[:]['Electric'] = True
        point_informationv2[:]['permittivity'] = 8.8541878176e-12
        point_informationv2[:]['permeability'] = 1.25663706212e-6
        # set position, velocity, normal, and weight of sources
        point_informationv2[0:num_sources]['px'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['py'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['pz'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 2]
        point_informationv2[0:num_sources]['nx'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['ny'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['nz'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 2]
        # point_informationv2[0:num_sources]['ex']=unified_weights[0:num_sources,0]
        # point_informationv2[0:num_sources]['ey']=unified_weights[0:num_sources,1]
        # point_informationv2[0:num_sources]['ez']=unified_weights[0:num_sources,2]
        # set position and velocity of sinks
        point_informationv2[num_sources:(num_sources + num_sinks)]['px'] = sinks[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['py'] = sinks[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['pz'] = sinks[:, 2]
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vx']=0.0
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vy']=0.0
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vz']=0.0
        point_informationv2[num_sources:(num_sources + num_sinks)]['nx'] = sink_normals[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['ny'] = sink_normals[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nz'] = sink_normals[:, 2]
        point_informationv2[(num_sources + num_sinks):]['px'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                0]
        point_informationv2[(num_sources + num_sinks):]['py'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                1]
        point_informationv2[(num_sources + num_sinks):]['pz'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                2]
        point_informationv2[(num_sources + num_sinks):]['nx'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                0]
        point_informationv2[(num_sources + num_sinks):]['ny'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                1]
        point_informationv2[(num_sources + num_sinks):]['nz'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                2]
        point_informationv2[:]['ex'] = unified_weights[:, 0]
        point_informationv2[:]['ey'] = unified_weights[:, 1]
        point_informationv2[:]['ez'] = unified_weights[:, 2]
        scatter_mask = np.zeros((point_informationv2.shape[0]), dtype=np.int32)
        scatter_mask[0:num_sources] = 0
        scatter_mask[(num_sources + num_sinks):] = scattering

    # full_index, initial_index = RF.integratedraycastersetup(num_sources,
    #                                                        num_sinks,
    #                                                        point_informationv2,
    #                                                        RF.convertTriangles(antenna_solid),
    #                                                        scatter_mask)
    full_index, rays = RF.workchunkingv2(np.asarray(aperture_coords.points).astype(np.float32),
                                         sinks,
                                         np.asarray(scatter_points.points).astype(np.float32),
                                         RF.convertTriangles(antenna_solid),
                                         scattering + 1)

    if ~elements:
        # create efiles for model
        etheta = np.zeros((el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        ephi = np.zeros((el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        Ex = np.zeros((el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        Ey = np.zeros((el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        Ez = np.zeros((el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        scatter_map = EM.EMGPUFreqDomain(num_sources,
                                         num_sinks,
                                         full_index,
                                         point_informationv2,
                                         wavelength)

        Ex[:, :] = np.sum(scatter_map[:, :, 0], axis=0).reshape(el_range.shape[0], az_range.shape[0])
        Ey[:, :] = np.sum(scatter_map[:, :, 1], axis=0).reshape(el_range.shape[0], az_range.shape[0])
        Ez[:, :] = np.sum(scatter_map[:, :, 2], axis=0).reshape(el_range.shape[0], az_range.shape[0])
        # convert to etheta,ephi
        etheta = Ex * np.cos(np.deg2rad(azaz)) * np.cos(np.deg2rad(theta)) + Ey * np.sin(np.deg2rad(azaz)) * np.cos(
            np.deg2rad(theta)) - Ez * np.sin(np.deg2rad(theta))
        ephi = -Ex * np.sin(np.deg2rad(azaz)) + Ey * np.cos(np.deg2rad(azaz))
    else:
        # create efiles for model
        etheta = np.zeros((num_sources, el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        ephi = np.zeros((num_sources, el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        Ex = np.zeros((num_sources, el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        Ey = np.zeros((num_sources, el_range.shape[0], az_range.shape[0]), dtype=np.complex64)
        Ez = np.zeros((num_sources, el_range.shape[0], az_range.shape[0]), dtype=np.complex64)

        for element in range(num_sources):
            point_informationv2[0:num_sources]['ex'] = 0.0
            point_informationv2[0:num_sources]['ey'] = 0.0
            point_informationv2[0:num_sources]['ez'] = 0.0
            point_informationv2[element]['ex'] = conformal_E_vectors[element, 0] / num_sources
            point_informationv2[element]['ey'] = conformal_E_vectors[element, 1] / num_sources
            point_informationv2[element]['ez'] = conformal_E_vectors[element, 2] / num_sources
            unified_weights[0:num_sources, :] = 0.0
            unified_weights[element, :] = conformal_E_vectors[element, :] / num_sources
            scatter_map = EM.EMGPUFreqDomain(num_sources,
                                             sinks.shape[0],
                                             full_index,
                                             point_informationv2,
                                             wavelength)
            Ex[element, :, :] = np.dot(np.ones((num_sources)), scatter_map[:, :, 0]).reshape(el_range.shape[0],
                                                                                             az_range.shape[0])
            Ey[element, :, :] = np.dot(np.ones((num_sources)), scatter_map[:, :, 1]).reshape(el_range.shape[0],
                                                                                             az_range.shape[0])
            Ez[element, :, :] = np.dot(np.ones((num_sources)), scatter_map[:, :, 2]).reshape(el_range.shape[0],
                                                                                             az_range.shape[0])
            etheta[element, :, :] = Ex[element, :, :] * np.cos(np.deg2rad(azaz)) * np.cos(np.deg2rad(theta)) + Ey[
                                                                                                               element,
                                                                                                               :,
                                                                                                               :] * np.sin(
                np.deg2rad(azaz)) * np.cos(np.deg2rad(theta)) - Ez[element, :, :] * np.sin(np.deg2rad(theta))
            ephi[element, :, :] = -Ex[element, :, :] * np.sin(np.deg2rad(azaz)) + Ey[element, :, :] * np.cos(
                np.deg2rad(azaz))

    return etheta, ephi


def calculate_scattering(aperture_coords,
                         sink_coords,
                         antenna_solid,
                         desired_E_axis,
                         scatter_points=None,
                         wavelength=1.0,
                         scattering=0,
                         elements=False,
                         los=True,
                         mesh_resolution=0.5,
                         project_vectors=False):
    """
    Based upon the aperture coordinates and solids, predict the farfield for the antenna.
    If line of sight scattering is not required then set los=False, such as if the transmit and receive antennas are the same
    """
    if desired_E_axis.size > 3:
        # multiple excitations requried
        multiE = True
    else:
        multiE = False

    num_sources = len(np.asarray(aperture_coords.points))
    num_sinks = len(np.asarray(sink_coords.points))

    if scattering == 0:
        # only use the aperture point cloud, no scattering required.
        scatter_points = o3d.geometry.PointCloud()

        if ~multiE:
            if project_vectors:
                conformal_E_vectors = EM.calculate_conformalVectors(desired_E_axis[0,:],
                                                                    np.asarray(aperture_coords.normals).astype(
                                                                        np.float32))
            else:
                conformal_E_vectors = np.repeat(desired_E_axis[0,:].astype(np.float32), num_sources,axis=0).reshape(num_sources,3)
        else:
            if project_vectors:
                conformal_E_vectors = EM.calculate_conformalVectors(desired_E_axis[0,:],
                                                                    np.asarray(aperture_coords.normals).astype(
                                                                        np.float32))
            else:
                conformal_E_vectors = np.repeat(desired_E_axis[0,:].astype(np.float32), num_sources,axis=0).reshape(num_sources,3)

        unified_model = np.append(np.asarray(aperture_coords.points).astype(np.float32),
                                  np.asarray(sink_coords.points).astype(np.float32), axis=0)
        unified_normals = np.append(np.asarray(aperture_coords.normals).astype(np.float32),
                                    np.asarray(sink_coords.normals).astype(np.float32), axis=0)
        unified_weights = np.ones((unified_model.shape[0], 3), dtype=np.complex64)
        unified_weights[0:num_sources,:] = conformal_E_vectors / num_sources  # set total amplitude to 1 for the aperture
        unified_weights[num_sources:num_sources + num_sinks,
        :] = 1 / num_sinks  # set total amplitude to 1 for the aperture
        point_informationv2 = np.empty((len(unified_model)), dtype=scattering_t)
        # set all sources as magnetic current sources, and permittivity and permeability as free space
        point_informationv2[:]['Electric'] = True
        point_informationv2[:]['permittivity'] = 8.8541878176e-12
        point_informationv2[:]['permeability'] = 1.25663706212e-6
        # set position, velocity, normal, and weight of sources
        point_informationv2[0:num_sources]['px'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['py'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['pz'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 2]
        point_informationv2[0:num_sources]['nx'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['ny'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['nz'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 2]
        # set position and velocity of sinks
        point_informationv2[num_sources:(num_sources + num_sinks)]['px'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['py'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['pz'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 2]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nx'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['ny'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nz'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 2]

        point_informationv2[:]['ex'] = unified_weights[:, 0]
        point_informationv2[:]['ey'] = unified_weights[:, 1]
        point_informationv2[:]['ez'] = unified_weights[:, 2]
        scatter_mask = np.zeros((point_informationv2.shape[0]), dtype=np.int32)
        scatter_mask[0:num_sources] = 0
        scatter_mask[(num_sources + num_sinks):] = 0

    else:
        # create scatter points on antenna solids based upon a half wavelength square
        if scatter_points is None:
            scatter_points, areas = TL.source_cloud_from_shape(antenna_solid, 1e-6, (wavelength * mesh_resolution) ** 2)

        if ~multiE:
            if project_vectors:
                conformal_E_vectors = EM.calculate_conformalVectors(desired_E_axis[0, :],
                                                                    np.asarray(aperture_coords.normals).astype(
                                                                        np.float32))
            else:
                conformal_E_vectors = np.repeat(desired_E_axis[0, :].astype(np.float32), num_sources, axis=0).reshape(num_sources,3)
        else:
            if project_vectors:
                conformal_E_vectors = EM.calculate_conformalVectors(desired_E_axis[0, :],
                                                                    np.asarray(aperture_coords.normals).astype(
                                                                        np.float32))
            else:
                conformal_E_vectors = np.repeat(desired_E_axis[0, :].astype(np.float32), num_sources, axis=0).reshape(num_sources,3)

        unified_model = np.append(np.append(np.asarray(aperture_coords.points).astype(np.float32),
                                            np.asarray(sink_coords.points).astype(np.float32), axis=0),
                                  np.asarray(scatter_points.points).astype(np.float32), axis=0)
        unified_normals = np.append(np.append(np.asarray(aperture_coords.normals).astype(np.float32),
                                              np.asarray(sink_coords.normals).astype(np.float32), axis=0),
                                    np.asarray(scatter_points.normals).astype(np.float32), axis=0)
        unified_weights = np.ones((unified_model.shape[0], 3), dtype=np.complex64)
        unified_weights[0:num_sources,:] = conformal_E_vectors / num_sources  # set total amplitude to 1 for the aperture
        unified_weights[num_sources:num_sources + num_sinks,:] = 1 / num_sinks  # set total amplitude to 1 for the aperture
        unified_weights[num_sources + num_sinks:, :] = 1.0# / len(np.asarray(scatter_points.points))  # set total amplitude to 1 for the aperture
        point_informationv2 = np.empty((len(unified_model)), dtype=scattering_t)
        # set all sources as magnetic current sources, and permittivity and permeability as free space
        point_informationv2[:]['Electric'] = True
        point_informationv2[:]['permittivity'] = 8.8541878176e-12
        point_informationv2[:]['permeability'] = 1.25663706212e-6
        # set position, velocity, normal, and weight of sources
        point_informationv2[0:num_sources]['px'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['py'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['pz'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 2]
        point_informationv2[0:num_sources]['nx'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['ny'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['nz'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 2]
        # point_informationv2[0:num_sources]['ex']=unified_weights[0:num_sources,0]
        # point_informationv2[0:num_sources]['ey']=unified_weights[0:num_sources,1]
        # point_informationv2[0:num_sources]['ez']=unified_weights[0:num_sources,2]
        # set position and velocity of sinks
        point_informationv2[num_sources:(num_sources + num_sinks)]['px'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['py'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['pz'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 2]
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vx']=0.0
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vy']=0.0
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vz']=0.0
        point_informationv2[num_sources:(num_sources + num_sinks)]['nx'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['ny'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nz'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 2]
        point_informationv2[(num_sources + num_sinks):]['px'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                0]
        point_informationv2[(num_sources + num_sinks):]['py'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                1]
        point_informationv2[(num_sources + num_sinks):]['pz'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                2]
        point_informationv2[(num_sources + num_sinks):]['nx'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                0]
        point_informationv2[(num_sources + num_sinks):]['ny'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                1]
        point_informationv2[(num_sources + num_sinks):]['nz'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                2]
        point_informationv2[:]['ex'] = unified_weights[:, 0]
        point_informationv2[:]['ey'] = unified_weights[:, 1]
        point_informationv2[:]['ez'] = unified_weights[:, 2]
        #scatter_mask = np.zeros((point_informationv2.shape[0]), dtype=np.int32)
        #scatter_mask[0:num_sources] = 0
        #scatter_mask[(num_sources + num_sinks):] = scattering

    # full_index, initial_index = RF.integratedraycastersetup(num_sources,
    #                                                        num_sinks,
    #                                                        point_informationv2,
    #                                                        RF.convertTriangles(antenna_solid),
    #                                                        scatter_mask)

    full_index, rays = RF.workchunkingv2(np.asarray(aperture_coords.points).astype(np.float32),
                                         np.asarray(sink_coords.points).astype(np.float32),
                                         np.asarray(scatter_points.points).astype(np.float32),
                                         RF.convertTriangles(antenna_solid), scattering + 1,line_of_sight=los)


    if (not elements):
        # create efiles for model
        if multiE:
            Ex = np.zeros((desired_E_axis.shape[0]), dtype=np.complex64)
            Ey = np.zeros((desired_E_axis.shape[0]), dtype=np.complex64)
            Ez = np.zeros((desired_E_axis.shape[0]), dtype=np.complex64)
            for e_inc in range(desired_E_axis.shape[0]):
                conformal_E_vectors = EM.calculate_conformalVectors(desired_E_axis[e_inc, :],
                                                                    np.asarray(aperture_coords.normals).astype(
                                                                        np.float32))
                unified_weights[0:num_sources, :] = conformal_E_vectors / num_sources
                point_informationv2[:]['ex'] = unified_weights[:, 0]
                point_informationv2[:]['ey'] = unified_weights[:, 1]
                point_informationv2[:]['ez'] = unified_weights[:, 2]
                scatter_map = EM.EMGPUFreqDomain(num_sources,
                                                 num_sinks,
                                                 full_index,
                                                 point_informationv2,
                                                 wavelength)
                Ex[e_inc] = np.sum(np.dot(np.ones((num_sources)), scatter_map[:, :, 0]))
                Ey[e_inc] = np.sum(np.dot(np.ones((num_sources)), scatter_map[:, :, 1]))
                Ez[e_inc] = np.sum(np.dot(np.ones((num_sources)), scatter_map[:, :, 2]))
        else:
            scatter_map = EM.EMGPUFreqDomain(num_sources,
                                             num_sinks,
                                             full_index,
                                             point_informationv2,
                                             wavelength)
            Ex = np.sum(np.dot(np.ones((num_sources)), scatter_map[:, :, 0]))
            Ey = np.sum(np.dot(np.ones((num_sources)), scatter_map[:, :, 1]))
            Ez = np.sum(np.dot(np.ones((num_sources)), scatter_map[:, :, 2]))

        # convert to etheta,ephi

    else:
        # create efiles for model
        if multiE:
            Ex = np.zeros((desired_E_axis.shape[1], num_sinks), dtype=np.complex64)
            Ey = np.zeros((desired_E_axis.shape[1], num_sinks), dtype=np.complex64)
            Ez = np.zeros((desired_E_axis.shape[1], num_sinks), dtype=np.complex64)
            for e_inc in range(desired_E_axis.shape[1]):
                conformal_E_vectors = EM.calculate_conformalVectors(desired_E_axis[e_inc, :],
                                                                    np.asarray(aperture_coords.normals).astype(
                                                                        np.float32))
                for element in range(num_sources):
                    point_informationv2[0:num_sources]['ex'] = 0.0
                    point_informationv2[0:num_sources]['ey'] = 0.0
                    point_informationv2[0:num_sources]['ez'] = 0.0
                    point_informationv2[element]['ex'] = conformal_E_vectors[element, 0] / num_sources
                    point_informationv2[element]['ey'] = conformal_E_vectors[element, 1] / num_sources
                    point_informationv2[element]['ez'] = conformal_E_vectors[element, 2] / num_sources
                    unified_weights[0:num_sources, :] = 0.0
                    unified_weights[element, :] = conformal_E_vectors[element, :] / num_sources
                    scatter_map = EM.EMGPUFreqDomain(num_sources,
                                                     num_sinks,
                                                     full_index,
                                                     point_informationv2,
                                                     wavelength)
                    Ex[element, :, e_inc] = np.dot(np.ones((num_sources)), scatter_map[:, :, 0])
                    Ey[element, :, e_inc] = np.dot(np.ones((num_sources)), scatter_map[:, :, 1])
                    Ez[element, :, e_inc] = np.dot(np.ones((num_sources)), scatter_map[:, :, 2])
        else:
            Ex = np.zeros((num_sources, num_sinks), dtype=np.complex64)
            Ey = np.zeros((num_sources, num_sinks), dtype=np.complex64)
            Ez = np.zeros((num_sources, num_sinks), dtype=np.complex64)
            for element in range(num_sources):
                point_informationv2[0:num_sources]['ex'] = 0.0
                point_informationv2[0:num_sources]['ey'] = 0.0
                point_informationv2[0:num_sources]['ez'] = 0.0
                point_informationv2[element]['ex'] = conformal_E_vectors[element, 0] / num_sources
                point_informationv2[element]['ey'] = conformal_E_vectors[element, 1] / num_sources
                point_informationv2[element]['ez'] = conformal_E_vectors[element, 2] / num_sources
                unified_weights[0:num_sources, :] = 0.0
                unified_weights[element, :] = conformal_E_vectors[element, :] / num_sources
                scatter_map = EM.EMGPUFreqDomain(num_sources,
                                                 num_sinks,
                                                 full_index,
                                                 point_informationv2,
                                                 wavelength)
                Ex[element, :] = np.dot(np.ones((num_sources)), scatter_map[:, :, 0])
                Ey[element, :] = np.dot(np.ones((num_sources)), scatter_map[:, :, 1])
                Ez[element, :] = np.dot(np.ones((num_sources)), scatter_map[:, :, 2])

    return Ex, Ey, Ez

def calculate_scattering_isotropic(aperture_coords,
                                   sink_coords,
                                   antenna_solid,
                                   scatter_points=None,
                                   wavelength=1.0,
                                   scattering=0,
                                   elements=False,
                                   mesh_resolution=0.5):
    """
    Based upon the aperture coordinates and solids, predict the farfield for the antenna.
    """
    num_sources = len(np.asarray(aperture_coords.points))
    num_sinks = len(np.asarray(sink_coords.points))

    if scattering == 0:
        # only use the aperture point cloud, no scattering required.
        scatter_points = o3d.geometry.PointCloud()

        unified_model = np.append(np.asarray(aperture_coords.points).astype(np.float32),
                                  np.asarray(sink_coords.points).astype(np.float32), axis=0)
        unified_normals = np.append(np.asarray(aperture_coords.normals).astype(np.float32),
                                    np.asarray(sink_coords.normals).astype(np.float32), axis=0)
        unified_weights = np.ones((unified_model.shape[0], 3), dtype=np.complex64)
        unified_weights[0:num_sources,:] = 1.0 / num_sources  # set total amplitude to 1 for the aperture
        unified_weights[num_sources:num_sources + num_sinks,
        :] = 1 / num_sinks  # set total amplitude to 1 for the aperture
        point_informationv2 = np.empty((len(unified_model)), dtype=scattering_t)
        # set all sources as magnetic current sources, and permittivity and permeability as free space
        point_informationv2[:]['Electric'] = True
        point_informationv2[:]['permittivity'] = 8.8541878176e-12
        point_informationv2[:]['permeability'] = 1.25663706212e-6
        # set position, velocity, normal, and weight of sources
        point_informationv2[0:num_sources]['px'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['py'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['pz'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 2]
        point_informationv2[0:num_sources]['nx'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['ny'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['nz'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 2]
        # set position and velocity of sinks
        point_informationv2[num_sources:(num_sources + num_sinks)]['px'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['py'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['pz'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 2]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nx'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['ny'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nz'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 2]

        point_informationv2[:]['ex'] = unified_weights[:, 0]
        point_informationv2[:]['ey'] = unified_weights[:, 1]
        point_informationv2[:]['ez'] = unified_weights[:, 2]
        scatter_mask = np.zeros((point_informationv2.shape[0]), dtype=np.int32)
        scatter_mask[0:num_sources] = 0
        scatter_mask[(num_sources + num_sinks):] = 0

    else:
        # create scatter points on antenna solids based upon a half wavelength square
        if scatter_points is None:
            scatter_points, areas = TL.source_cloud_from_shape(antenna_solid, 1e-6, (wavelength * mesh_resolution) ** 2)

        unified_model = np.append(np.append(np.asarray(aperture_coords.points).astype(np.float32),
                                            np.asarray(sink_coords.points).astype(np.float32), axis=0),
                                  np.asarray(scatter_points.points).astype(np.float32), axis=0)
        unified_normals = np.append(np.append(np.asarray(aperture_coords.normals).astype(np.float32),
                                              np.asarray(sink_coords.normals).astype(np.float32), axis=0),
                                    np.asarray(scatter_points.normals).astype(np.float32), axis=0)
        unified_weights = np.ones((unified_model.shape[0], 3), dtype=np.complex64)
        unified_weights[0:num_sources,:] = 1.0 / num_sources  # set total amplitude to 1 for the aperture
        unified_weights[num_sources:num_sources + num_sinks,:] = 1 / num_sinks  # set total amplitude to 1 for the aperture
        unified_weights[num_sources + num_sinks:, :] = 1.0# / len(np.asarray(scatter_points.points))  # set total amplitude to 1 for the aperture
        point_informationv2 = np.empty((len(unified_model)), dtype=scattering_t)
        # set all sources as magnetic current sources, and permittivity and permeability as free space
        point_informationv2[:]['Electric'] = True
        point_informationv2[:]['permittivity'] = 8.8541878176e-12
        point_informationv2[:]['permeability'] = 1.25663706212e-6
        # set position, velocity, normal, and weight of sources
        point_informationv2[0:num_sources]['px'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['py'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['pz'] = np.asarray(aperture_coords.points).astype(np.float32)[:, 2]
        point_informationv2[0:num_sources]['nx'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 0]
        point_informationv2[0:num_sources]['ny'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 1]
        point_informationv2[0:num_sources]['nz'] = np.asarray(aperture_coords.normals).astype(np.float32)[:, 2]
        # point_informationv2[0:num_sources]['ex']=unified_weights[0:num_sources,0]
        # point_informationv2[0:num_sources]['ey']=unified_weights[0:num_sources,1]
        # point_informationv2[0:num_sources]['ez']=unified_weights[0:num_sources,2]
        # set position and velocity of sinks
        point_informationv2[num_sources:(num_sources + num_sinks)]['px'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['py'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['pz'] = np.asarray(sink_coords.points).astype(
            np.float32)[:, 2]
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vx']=0.0
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vy']=0.0
        # point_informationv2[num_sources:(num_sources+num_sinks)]['vz']=0.0
        point_informationv2[num_sources:(num_sources + num_sinks)]['nx'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 0]
        point_informationv2[num_sources:(num_sources + num_sinks)]['ny'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 1]
        point_informationv2[num_sources:(num_sources + num_sinks)]['nz'] = np.asarray(sink_coords.normals).astype(
            np.float32)[:, 2]
        point_informationv2[(num_sources + num_sinks):]['px'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                0]
        point_informationv2[(num_sources + num_sinks):]['py'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                1]
        point_informationv2[(num_sources + num_sinks):]['pz'] = np.asarray(scatter_points.points).astype(np.float32)[:,
                                                                2]
        point_informationv2[(num_sources + num_sinks):]['nx'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                0]
        point_informationv2[(num_sources + num_sinks):]['ny'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                1]
        point_informationv2[(num_sources + num_sinks):]['nz'] = np.asarray(scatter_points.normals).astype(np.float32)[:,
                                                                2]
        point_informationv2[:]['ex'] = unified_weights[:, 0]
        point_informationv2[:]['ey'] = unified_weights[:, 1]
        point_informationv2[:]['ez'] = unified_weights[:, 2]
        scatter_mask = np.zeros((point_informationv2.shape[0]), dtype=np.int32)
        scatter_mask[0:num_sources] = 0
        scatter_mask[(num_sources + num_sinks):] = scattering

    # full_index, initial_index = RF.integratedraycastersetup(num_sources,
    #                                                        num_sinks,
    #                                                        point_informationv2,
    #                                                        RF.convertTriangles(antenna_solid),
    #                                                        scatter_mask)
    full_index, rays = RF.workchunkingv2(np.asarray(aperture_coords.points).astype(np.float32),
                                         np.asarray(sink_coords.points).astype(np.float32),
                                         np.asarray(scatter_points.points).astype(np.float32),
                                         RF.convertTriangles(antenna_solid), scattering + 1)

    if (not elements):
        # create efiles for model
            scatter_map = EM.IsoGPUFreqDomain(num_sources,
                                              num_sinks,
                                              full_index,
                                              point_informationv2,
                                              wavelength)
            final_scattering_map = np.sum(np.dot(np.ones((num_sources)), scatter_map[:, :, 0]))

        # convert to etheta,ephi

    else:
        # create efiles for model

        final_scattering_map = np.zeros((num_sources, num_sinks), dtype=np.complex64)

        for element in range(num_sources):
            point_informationv2[0:num_sources]['ex'] = 0.0
            point_informationv2[0:num_sources]['ey'] = 0.0
            point_informationv2[0:num_sources]['ez'] = 0.0
            point_informationv2[element]['ex'] = 1.0 / num_sources
            point_informationv2[element]['ey'] = 1.0 / num_sources
            point_informationv2[element]['ez'] = 1.0 / num_sources
            unified_weights[0:num_sources, :] = 0.0
            unified_weights[element, :] = 1.0 / num_sources
            scatter_map = EM.EMGPUFreqDomain(num_sources,
                                             num_sinks,
                                             full_index,
                                             point_informationv2,
                                             wavelength)
            final_scattering_map[element, :] = np.dot(np.ones((num_sources)), scatter_map[:, :, 0])

    return final_scattering_map