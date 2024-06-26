#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use 
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import os
import random
import json
from utils.system_utils import searchForMaxIteration
from scene.dataset_readers import sceneLoadTypeCallbacks
from scene.gaussian_model import GaussianModel
from arguments import ModelParams
from utils.camera_utils import cameraList_from_camInfos, camera_to_JSON

class PartedScene:
    def __init__(self, cameras, name) -> None:
        self.name = name
        
        # filename = "./scene/cameras.json"
        # filename = "D:/work/projects/iann-gaussian-splatting-data/matrix_city_for_tiled_gss/parted/images.json.00"
        
        # with open(filename, 'r') as file:
        #     json_data = json.load(file)
            
        #     self.selected_cameras = [False for i in range(0, 1055)]
        #     for i in json_data:
        #         for j in range(0, 1055):
        #             if i["img_name"] == cameras[j].image_name:
        #                 self.selected_cameras[j] = True
        self.selected_cameras = [False for i in range(0, len(cameras))]
        
        # filename = "D:/work/projects/iann-gaussian-splatting-data/matrix_city_for_tiled_gss/parted/{}.json".format(name)
        # with open(filename, 'r') as file:
        #     json_data = json.load(file)
        #     self.bounds = [ json_data[0]["min"], json_data[0]["max"] ]
           
        #     cameras_name_who_can_see_the_tile = json_data[0]["cameras_name_who_can_see_the_tile"]
            
            
        #     for i in cameras_name_who_can_see_the_tile:
        #         for j in range(0, 1055):
        #             if i[:4] == cameras[j].image_name:
        #                 self.selected_cameras[j] = True
                        
    def load_from_json(self, cameras, json_data):
        self.name = json_data["name"]
        self.bounds = [ json_data["min"], json_data["max"] ]
        cameras_name_who_can_see_the_tile = json_data["cameras_name_who_can_see_the_tile"]
        self.selected_cameras = [False for i in range(0, len(cameras))]
        for i in cameras_name_who_can_see_the_tile:
            for j in range(0, len(cameras)):
                if i[:4] == cameras[j].image_name:
                    self.selected_cameras[j] = True
        


    
class Scene:

    # gaussians : GaussianModel

    def __init__(self, args : ModelParams, load_iteration=None, shuffle=True, resolution_scales=[1.0]):
        """b
        :param path: Path to colmap scene main folder.
        """
        
        self.args = args
        self.model_path = args.model_path
        self.loaded_iter = None
        # self.gaussians = gaussians
       
        if load_iteration:
            if load_iteration == -1:
                self.loaded_iter = searchForMaxIteration(os.path.join(self.model_path, "point_cloud"))
            else:
                self.loaded_iter = load_iteration
            print("Loading trained model at iteration {}".format(self.loaded_iter))

        self.train_cameras = {}
        self.test_cameras = {}

        if os.path.exists(os.path.join(args.source_path, "sparse")):
            scene_info = sceneLoadTypeCallbacks["Colmap"](args.source_path, args.images, args.eval)
        elif os.path.exists(os.path.join(args.source_path, "transforms_train.json")):
            print("Found transforms_train.json file, assuming Blender data set!")
            scene_info = sceneLoadTypeCallbacks["Blender"](args.source_path, args.white_background, args.eval)
        else:
            assert False, "Could not recognize scene type!"

        if not self.loaded_iter:
            with open(scene_info.ply_path, 'rb') as src_file, open(os.path.join(self.model_path, "input.ply") , 'wb') as dest_file:
                dest_file.write(src_file.read())
            json_cams = []
            camlist = []
            if scene_info.test_cameras:
                camlist.extend(scene_info.test_cameras)
            if scene_info.train_cameras:
                camlist.extend(scene_info.train_cameras)
            for id, cam in enumerate(camlist):
                json_cams.append(camera_to_JSON(id, cam))
            with open(os.path.join(self.model_path, "cameras.json"), 'w') as file:
                json.dump(json_cams, file)

        if shuffle:
            random.shuffle(scene_info.train_cameras)  # Multi-res consistent random shuffling
            random.shuffle(scene_info.test_cameras)  # Multi-res consistent random shuffling

        self.cameras_extent = scene_info.nerf_normalization["radius"]
        self.cameras_extent = 2.37

        for resolution_scale in resolution_scales:
            print("Loading Training Cameras")
            self.train_cameras[resolution_scale] = cameraList_from_camInfos(scene_info.train_cameras, resolution_scale, args)
            print("Loading Test Cameras")
            self.test_cameras[resolution_scale] = cameraList_from_camInfos(scene_info.test_cameras, resolution_scale, args)

        self.point_cloud = scene_info.point_cloud

            
        # self.part = PartedScene(self.train_cameras[1.0])
        self.parts = []
        # self.parts.append(PartedScene(self.train_cameras[1.0], name="part_00"))
        # self.parts.append(PartedScene(self.train_cameras[1.0], name="part_01"))
        self.load_parts()

    def save(self, part, iteration):
        point_cloud_path = os.path.join(self.model_path, "point_cloud/iteration_{}".format(iteration))
        point_cloud_name = "point_cloud.ply.{}".format(part.name)
        clipped_point_cloud_name = "point_cloud.ply.{}.clip".format(part.name)
        bounds = part.bounds if hasattr(part, "bounds") else None
        self.gaussians.save_ply(os.path.join(point_cloud_path, clipped_point_cloud_name ), bounds=bounds)
        self.gaussians.save_ply(os.path.join(point_cloud_path, point_cloud_name))

    # def getTrainCameras(self, scale=1.0):
    #     return self.train_cameras[scale]
    
    def getTrainCameras(self, part, scale=1.0):
        cameras = []
        for i in range(len(self.train_cameras[scale])):
            if part.selected_cameras[i]:
                cameras.append(self.train_cameras[scale][i])
        
        # print("Selected Cameras: ")
        # for c in cameras:
        #     print(c.image_name)
        # print("Randomly Shuffled Cameras: ")
        # random.shuffle(cameras)
        # for c in cameras:
        #     print(c.image_name)
        return cameras

    def getTestCameras(self, scale=1.0):
        return self.test_cameras[scale]
    
    def getGaussianmodel(self,part):
        self.gaussians = GaussianModel(self.args.sh_degree)

        if self.loaded_iter:
            self.gaussians.load_ply(os.path.join(self.model_path,
                                                           "point_cloud",
                                                           "iteration_" + str(self.loaded_iter),
                                                           "point_cloud.ply"))
        else:
            self.gaussians.create_from_pcd(self.point_cloud, self.cameras_extent)
        return self.gaussians
    
    def merge_parts_and_save(self, iteration):
        point_cloud_pathname = os.path.join(self.model_path, "point_cloud/iteration_{}".format(iteration), "point_cloud.ply")
        
        from plyfile import PlyData, PlyElement
        import numpy as np
        
        input_files = []
        for part in self.parts:
            input_files.append(os.path.join(self.model_path, "point_cloud/iteration_{}/point_cloud.ply.{}.clip".format(iteration, part.name)))
       
        combined_vertices = []
        for input_file in input_files:
            # Read the current PLY file
            ply_data = PlyData.read(input_file)
            
            # Append vertices from the current file
            combined_vertices.append(ply_data['vertex'].data)
        
        # Combine the vertex data
        combined_vertices = np.concatenate(combined_vertices)
        ply_elements = [PlyElement.describe(combined_vertices, 'vertex')]
        merged_ply = PlyData(ply_elements)
        merged_ply.write(point_cloud_pathname)
        
    def load_parts(self):
        filename = os.path.join(self.args.source_path, "parted/parts.json")
        with open(filename, 'r') as file:
            json_data = json.load(file)
            for i in json_data:
                part = PartedScene(self.train_cameras[1.0], "")
                part.load_from_json(self.train_cameras[1.0], i)
                self.parts.append(part)
    def clear_viewpoints_cache(self):
        for viewpoint in self.train_cameras[1.0]:
            viewpoint.original_image = None