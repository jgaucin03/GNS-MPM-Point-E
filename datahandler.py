import os
import numpy as np
import matplotlib.pyplot as plt
import json
from tqdm import tqdm
#import pickle
#import torch
#import open3d as o3d

class TrajectoryDataHandler:
    def __init__(self, directory):
        self.directory = directory

    def load_npz(self, file_path):
        return np.load(file_path, allow_pickle=True)
    
    def load_pkl(self, file_path):
        """Load data from a .pkl file."""
        with open(file_path, 'rb') as file:
            data = pickle.load(file)
        return data

    def inspect_trajectory(self, data, key):
        trajectory_data = data[key]
        positions = trajectory_data[0]
        particle_types = trajectory_data[1]

        # Optional: Check if material_properties are present
        if len(trajectory_data) > 2:
            material_properties = trajectory_data[2]
            print(f"Material properties shape: {material_properties.shape}")

        # Extracting the shape information
        n_timesteps, n_particles, n_dims = positions.shape

        print(f"Trajectory: {key}")
        print(f"Positions shape: {positions.shape}")
        print(f"Number of time steps: {n_timesteps}")
        print(f"Number of particles: {n_particles}")
        print(f"Number of dimensions: {n_dims}")
        print(f"Particle types shape: {particle_types.shape}")
        print(f"First few particle types: {particle_types[:10]}")
        print()

        return n_particles

    def inspect_npz_file(self, file_name):
        file_path = os.path.join(self.directory, file_name)
        data = self.load_npz(file_path)

        total_samples = 0 # Total samples in data_loader.py is the number of particles across each trajectory not counting input sequence length
        num_particles_list = []

        for key in data.files:
            num_particles = self.inspect_trajectory(data, key)
            total_samples += num_particles
            num_particles_list.append(num_particles)

        print(f"Total samples (Particles across each trajectory): {total_samples}")

        # Plotting the number of particles for each trajectory
        """ plt.figure(figsize=(10, 6))
        plt.plot(range(len(num_particles_list)), num_particles_list, marker='o', linestyle='-', color='b')
        plt.xlabel('Trajectory Index')
        plt.ylabel('Number of Particles')
        plt.title('Number of Particles in Each Trajectory')
        plt.grid(True)
        plt.show() """
        
    def inspect_pkl_file(self, file_name):
        """Inspect the keys and their types in a .pkl file."""
        file_path = os.path.join(self.directory, file_name)
        data = self.load_pkl(file_path)

        if not isinstance(data, dict):
            print("Unexpected data structure in .pkl file")
            return

        # Display keys and their types
        print("Keys and their types in the .pkl file:")
        for key, value in data.items():
            print(f"Key: {key}, Type: {type(value)}")
            if key == 'particle_types':
                print(value)
    
    def convert_pkl_to_npz(self, pkl_path, npz_path):
        data = self.load_pkl(pkl_path)
        # Convert PyTorch tensors to NumPy arrays and save as .npz
        converted_data = {key: value.cpu().numpy() if isinstance(value, torch.Tensor) else value
                        for key, value in data.items()}
        
        # Save as .npz file
        np.savez(npz_path, **converted_data)

    def merge_trajectories(self, output_file_name, num_trajectories=10):
        combined_trajectories = {}

        for i in range(num_trajectories):
            file_path = os.path.join(self.directory, f"trajectory{i}.npz")
            with self.load_npz(file_path) as data:
                key = f"trajectory{i}"
                positions, particle_types = data[key]
                combined_trajectories[f"simulation_trajectory_{i}"] = (positions, particle_types)

        output_file = os.path.join(self.directory, output_file_name)
        print("Compressing npz...")
        np.savez_compressed(output_file, **combined_trajectories)
        print(f"Combined trajectories saved to {output_file}")
        
    # Calculate metadata for a merged npz file:
    
    def create_metadata(self, output_file_name, num_trajectories=10, sequence_length=350, default_connectivity_radius=0.025, dim=3, material_feature_len=0, dt_mpm=0.0025, dt_gns=1.0):
        bounds = [[0.1, 0.9], [0.1, 0.9], [0.1, 0.9]]
        mpm_cell_size = [None, None, None]
        nparticles_per_cell = None

        trajectories = {}
        
        # data_names = []
        cumulative_count = 0
        cumulative_sum_vel = np.zeros((1, dim))
        cumulative_sum_acc = np.zeros((1, dim))
        cumulative_sumsq_vel = np.zeros((1, dim))
        cumulative_sumsq_acc = np.zeros((1, dim))

        for i in tqdm(range(num_trajectories)):
            data_name = f"trajectory{i}"
            # Not necessary to keep track of this for metadata
            # data_names.append(data_name)
            npz_path = os.path.join(self.directory, f"{data_name}.npz")
            data = self.load_npz(npz_path)
            for simulation_id, trajectory in data.items():
                trajectories[f"simulation_trajectory_{i}"] = (trajectory)

            positions = trajectory[0]
            array_shape = positions.shape
            flattened_positions = np.reshape(positions, (-1, array_shape[-1]))

            velocities = np.empty_like(positions)
            velocities[1:] = (positions[1:] - positions[:-1]) / dt_gns
            velocities[0] = 0
            flattened_velocities = np.reshape(velocities, (-1, array_shape[-1]))

            accelerations = np.empty_like(velocities)
            accelerations[1:] = (velocities[1:] - velocities[:-1]) / dt_gns
            accelerations[0] = 0
            flattened_accelerations = np.reshape(accelerations, (-1, array_shape[-1]))

            cumulative_count += len(flattened_velocities)
            cumulative_sum_vel += np.sum(flattened_velocities, axis=0)
            cumulative_sum_acc += np.sum(flattened_accelerations, axis=0)
            cumulative_sumsq_vel += np.sum(flattened_velocities**2, axis=0)
            cumulative_sumsq_acc += np.sum(flattened_accelerations**2, axis=0)
            cumulative_mean_vel = cumulative_sum_vel / cumulative_count
            cumulative_mean_acc = cumulative_sum_acc / cumulative_count
            cumulative_std_vel = np.sqrt(
                (cumulative_sumsq_vel / cumulative_count - (cumulative_sum_vel / cumulative_count)**2))
            cumulative_std_acc = np.sqrt(
                (cumulative_sumsq_acc / cumulative_count - (cumulative_sum_acc / cumulative_count)**2))

        statistics = {
            "mean_velocity_x": float(cumulative_mean_vel[:, 0]),
            "mean_velocity_y": float(cumulative_mean_vel[:, 1]),
            "mean_velocity_z": float(cumulative_mean_vel[:, 2]),
            "std_velocity_x": float(cumulative_std_vel[:, 0]),
            "std_velocity_y": float(cumulative_std_vel[:, 1]),
            "std_velocity_z": float(cumulative_std_vel[:, 2]),
            "mean_accel_x": float(cumulative_mean_acc[:, 0]),
            "mean_accel_y": float(cumulative_mean_acc[:, 1]),
            "mean_accel_z": float(cumulative_mean_acc[:, 2]),
            "std_accel_x": float(cumulative_std_acc[:, 0]),
            "std_accel_y": float(cumulative_std_acc[:, 1]),
            "std_accel_z": float(cumulative_std_acc[:, 2])
        }

        for key, value in statistics.items():
            print(f"{key}: {value:.7E}")
        ## Note: In GNS train.py: 
        # Default Boundary Augment (1.0), no 'Default' connectivity radius (0.025), default sequence_length default is found from positions.shape[1]
        # Default nnode_in is 37 if 3D else 30, default nedge_in is 1 + dimensions (e. g. 3 + 1 = 4 nedge_in)
        ## Not used: material_feature_len, dt, mpm_cell_size, nparticles_per_cell, data_names
        metadata = {
            "bounds": bounds,
            "sequence_length": sequence_length,
            "default_connectivity_radius": default_connectivity_radius,
            "boundary_augment": 1.0,
            "material_feature_len": material_feature_len,
            "dim": dim,
            "dt": dt_mpm,
            "vel_mean": [statistics["mean_velocity_x"], statistics["mean_velocity_y"], statistics["mean_velocity_z"]],
            "vel_std": [statistics["std_velocity_x"], statistics["std_velocity_y"], statistics["std_velocity_z"]],
            "acc_mean": [statistics["mean_accel_x"], statistics["mean_accel_y"], statistics["mean_accel_z"]],
            "acc_std": [statistics["std_accel_x"], statistics["std_accel_y"], statistics["std_accel_z"]],
            "mpm_cell_size": mpm_cell_size,
            "nparticles_per_cell": nparticles_per_cell,
        }

        metadata_file_path = os.path.join(self.directory, f"{output_file_name}.json")
        # Open the metadata json file, make it if it doesn't exist
        with open(metadata_file_path, "w") as fp:
            json.dump(metadata, fp)
        print(f"metadata saved at: {metadata_file_path}")
        
class PointcloudDataHandler:
    def __init__(self, pc_directory):
        self.pc_directory = pc_directory

    def create_ply(self, file_path):
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        ply_header = """ply
                    format ascii 1.0
                    element vertex 0
                    property float x
                    property float y
                    property float z
                    end_header
                    """
        with open(file_path, 'w') as f:
            f.write(ply_header)
        print(f"Empty .ply file created at: {file_path}")
        
    # Inspect values of the pointcloud
    def inspect_pointcloud(self, filename):
        # Read the pointcloud file
        pc_path = os.path.join(self.pc_directory, filename)
        if not os.path.exists(pc_path):
            raise ValueError(f"Pointcloud file {pc_path} does not exist.")
        pcd = o3d.io.read_point_cloud(pc_path)
        points = np.asarray(pcd.points)

        # Find the max and min values for x, y, and z
        min_vals = points.min(axis=0)
        max_vals = points.max(axis=0)
        num_points = points.shape[0]

        print(f"Minimum values: {min_vals}")
        print(f"Maximum values: {max_vals}")
        print(f"Number of points: {num_points}")
    
    # Center the pointcloud within a given domain 
    def center_pc(self, filename, domain_size):
        pc_path = os.path.join(self.pc_directory, filename)
        if not os.path.exists(pc_path):
            raise ValueError(f"Pointcloud file {pc_path} does not exist.")
        
        # Read the pointcloud file
        pcd = o3d.io.read_point_cloud(pc_path)
        points = np.asarray(pcd.points)

        # Calculate the centroid of the pointcloud
        centroid = points.mean(axis=0)

        # Calculate the domain center
        domain_center = np.array([np.mean(d) for d in domain_size])

        # Center the pointcloud
        centered_points = points - centroid + domain_center

        # Create a new point cloud with the centered points
        centered_pcd = o3d.geometry.PointCloud()
        centered_pcd.points = o3d.utility.Vector3dVector(centered_points)

        # Save the centered pointcloud to a new .ply file
        base, ext = os.path.splitext(pc_path)
        centered_pc_path = f"{base}-centered{ext}"
        o3d.io.write_point_cloud(centered_pc_path, centered_pcd, write_ascii=True)
        
        print(f"Centered pointcloud saved to: {centered_pc_path}")
        return centered_pc_path
    
    # Scale the pointcloud to a specified percentage of its original size
    def scale_pc(self, filename, scale_percentage):
        pc_path = os.path.join(self.pc_directory, filename)
        if not os.path.exists(pc_path):
            raise ValueError(f"Pointcloud file {pc_path} does not exist.")

        # Read the pointcloud file
        pcd = o3d.io.read_point_cloud(pc_path)
        points = np.asarray(pcd.points)

        # Calculate the centroid of the pointcloud
        centroid = points.mean(axis=0)

        # Scale the pointcloud
        scaled_points = (points - centroid) * scale_percentage + centroid

        # Create a new point cloud with the scaled points
        scaled_pcd = o3d.geometry.PointCloud()
        scaled_pcd.points = o3d.utility.Vector3dVector(scaled_points)

        # Save the scaled pointcloud to a new .ply file
        base, ext = os.path.splitext(pc_path)
        scaled_pc_path = f"{base}-scaled{ext}"
        o3d.io.write_point_cloud(scaled_pc_path, scaled_pcd, write_ascii=True)
        
        print(f"Scaled pointcloud saved to: {scaled_pc_path}")
        return scaled_pc_path
    
    def downsample_ply(self, filename, target_number_of_points=5000):
        pc_path = os.path.join(self.pc_directory, filename)
        if not os.path.exists(pc_path):
            raise ValueError(f"Pointcloud file {pc_path} does not exist.")
        
        # Load the point cloud from the PLY file
        pcd = o3d.io.read_point_cloud(pc_path)
        
        # Get the total number of points in the original point cloud
        original_points = np.asarray(pcd.points).shape[0]
        
        # Estimate initial voxel size (this is a rough estimation and might need adjustment)
        voxel_size = (pcd.get_max_bound() - pcd.get_min_bound()).max() * (original_points / target_number_of_points) ** (1/3)
        
        # Downsample the point cloud
        downsampled_pcd = pcd.voxel_down_sample(voxel_size)
        
        minimum_threshold = 0.0005  # Minimum voxel size
        # After initial downsampling
        if np.asarray(downsampled_pcd.points).shape[0] < target_number_of_points:
            while np.asarray(downsampled_pcd.points).shape[0] < target_number_of_points:
                voxel_size *= 0.9  # Decrease voxel size by 10%
                downsampled_pcd = pcd.voxel_down_sample(voxel_size)
                if voxel_size < minimum_threshold:  # Prevent voxel size from becoming too small
                    break
        # Optionally, save the downsampled point cloud to a new PLY file
        file = os.path.splitext(pc_name)[0]
        down_filename = f"{file}-downsampled.ply"
        output_path = os.path.join(self.pc_directory, down_filename)
        self.create_ply(output_path)
        o3d.io.write_point_cloud(output_path, downsampled_pcd, write_ascii=True)
    
        return down_filename
    
    # Preprocess pointcloud to fit inside of MPM simulation domain
    def preprocess_pointcloud(self, filename, output_path, domain_size, target_occupancy=0.4, point_e_rotation=False):
        # Join the directory and filename
        pc_path = os.path.join(self.pc_directory, filename)
        if not os.path.exists(pc_path):
            raise ValueError(f"Pointcloud file {pc_path} does not exist.")
        
        # Read the point cloud
        pcd = o3d.io.read_point_cloud(pc_path)
        
        # Remove outliers
        cl, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        pcd = pcd.select_by_index(ind)

        # Calculate initial properties
        bbox = pcd.get_axis_aligned_bounding_box()
        current_dimensions = bbox.get_extent()
        centroid = bbox.get_center()
        
        print(f"Current bounding box: {bbox}")
        print(f"Current dimensions: {current_dimensions}")
        print(f"Current centroid: {centroid}")

        if point_e_rotation:
            # Rotate the point cloud 90 degrees about the y-axis, and 180 about x-axis (Point-E)
            R = pcd.get_rotation_matrix_from_xyz((np.pi / 2, np.pi, 0))
        else:
            # Custom rotation
            R = pcd.get_rotation_matrix_from_xyz((0, 0, np.pi))
            
        pcd.rotate(R, center=centroid)

        # Calculate target dimensions (40% of domain size)
        domain_extent = np.array([d[1] - d[0] for d in domain_size])
        target_dimensions = domain_extent * target_occupancy

        # Determine scaling factor
        scaling_factors = target_dimensions / current_dimensions
        scale_factor = min(scaling_factors)

        # Scale the point cloud
        pcd.scale(scale_factor, center=centroid)

        # Move the point cloud to the ground (lowest y value to the lowest y value of the domain)
        bbox = pcd.get_axis_aligned_bounding_box()
        min_bound = bbox.get_min_bound()
        translation = [0, domain_size[1][0] - min_bound[1], 0]
        pcd.translate(translation)

        # Recalculate properties after rotation, scaling, and translation
        bbox = pcd.get_axis_aligned_bounding_box()
        current_dimensions = bbox.get_extent()
        centroid = bbox.get_center()
        
        print(f"Bounding box after rotation, scaling, and translation: {bbox}")
        print(f"Dimensions after rotation, scaling, and translation: {current_dimensions}")
        print(f"Centroid after rotation, scaling, and translation: {centroid}")

        # Center the point cloud in the domain horizontally
        new_centroid = np.mean(domain_size, axis=1)
        translation = [new_centroid[0] - centroid[0], 0, new_centroid[2] - centroid[2]]
        pcd.translate(translation)

        print(f"Final bounding box: {pcd.get_axis_aligned_bounding_box()}")
        print(f"Final dimensions: {bbox.get_extent()}")
        print(f"Final centroid: {new_centroid}")
        
        # Create an empty.ply file
        self.create_ply(output_path)
        # Save the preprocessed point cloud
        o3d.io.write_point_cloud(output_path, pcd, write_ascii=True)
    

    
# Example usage
if __name__ == "__main__":
    NPZ = False
    PC = False
    PKL = False
    if NPZ:
        npz_directory = "/scratch/10029/jgaucin/gns-mpm-ls6/gns/gns-samples/Sand/dataset"
        # Initialize instance of data handler using base directory {npz_directory}
        handler = TrajectoryDataHandler(npz_directory)

        # Inspect specific .npz files
        print("Inspecting train.npz")
        handler.inspect_npz_file("train.npz")
        print("Inspecting test.npz")
        handler.inspect_npz_file("test.npz")
        print("Inspecting valid.npz")
        handler.inspect_npz_file("valid.npz")
        
        # Necessary metadata (9):
        # {"bounds","sequence_length", "default_connectivity_radius","dim", "dt", "vel_mean", "vel_std", "acc_mean", "acc_std"}
        # Note: In GNS train.py sequence_length not necessary but recommended and dt is not necessary, only describing MPM simulation timesteps.
    elif PC:
        Downsample = False
        PC_Directory = "/scratch/10029/jgaucin/gns-mpm-ls6/point-e/generated_pc"
        pcdh = PointcloudDataHandler(PC_Directory)
        pc_name = "red_motor0.ply"
        pcdh.inspect_pointcloud(pc_name)
        if Downsample:
            pc_name = pcdh.downsample_ply(pc_name)
        domain = [[0.1,0.9],[0.1,0.9],[0.1,0.9]]
        output_path = f"/scratch/10029/jgaucin/gns-mpm-ls6/taichi_mpm_water/test_pc2/{pc_name}"
        pcdh.preprocess_pointcloud(pc_name, output_path, domain, 0.6, True)
    
    elif PKL:
        PKL_Directory = "/scratch/10029/jgaucin/gns-mpm-ls6/gns/gns-samples/WaterBarrier/rollout"
        handler = TrajectoryDataHandler(PKL_Directory)
        # Inspect the .pkl file
        print("Converting pkl to npz")
        handler.convert_pkl_to_npz("/scratch/10029/jgaucin/gns-mpm-ls6/gns/gns-samples/WaterBarrier/rollout/rollout_ex0.pkl", "/scratch/10029/jgaucin/gns-mpm-ls6/taichi_mpm_water/test_pc_reservoir/gns_reservoir_rollout.npz")