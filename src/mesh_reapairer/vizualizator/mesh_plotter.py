from __future__ import annotations

from mesh_reapairer.msu import Mesh
from mesh_reapairer.vizualizator.segment_plotter import *
from mesh_reapairer.vizualizator.face_plotter import *

from mesh_reapairer.self_intersection_finder.intersection_finder import Segment
from mesh_reapairer.self_intersection_finder.bvh_builder import *

def plot_mesh(mesh: Mesh,
              faces_enable: bool = True,
              faces_color: str = "",
              edges_enable: bool = False,
              edges_linewidths: float = 0.3,
              aabb_boxes_enable:bool = False,
              faces_label_enable: bool = False,
              faces_alpha: float = 0.3,
              faces_plane_enable: bool = False,
              faces_plane_size: float = 1.0,
              faces_plane_alpha: float = 0.1,
              intersection_segments_enable: bool = False,
              intersection_segments: List[Segment] = [],
              intersection_segments_linewidths: float = 1.0,
              intersection_segments_color: str = "red",
              border_enable: bool = False,
              border_faces: List[Face] = False,
              border_faces_alpha: float = 0.5,
              border_color: str = "blue"
              ) -> None:
    
    zones = list({zone.name for zone in mesh.zones})
    colors = np.random.rand(len(zones), 3)
    color_map = {z: c for z, c in zip(zones, colors)}
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    if faces_enable:
        for face in mesh.faces:
            plot_face(ax=ax,
                    face=face, 
                    color=faces_color if faces_color else color_map.get(face.zone.name), 
                    edges_enable=edges_enable, 
                    edges_linewidths=edges_linewidths, 
                    draw_aabb=aabb_boxes_enable, 
                    label=faces_label_enable, 
                    alpha=faces_alpha, 
                    plane=faces_plane_enable, 
                    plane_size=faces_plane_size,
                    plane_alpha=faces_plane_alpha)
            
    if intersection_segments_enable:
        if not intersection_segments:
            raise ValueError("mesh_plotter: intersection_segments not set but draw")
        for segment in intersection_segments:
            plot_segment(ax=ax, 
                         nodes=segment.nodes, 
                         color=intersection_segments_color, 
                         linewidths=intersection_segments_linewidths)
    
    if border_enable:
        if not border_faces:
            raise ValueError("mesh_plotter: border_faces not set but draw")
        for border_face in border_faces:
            plot_face(ax=ax,
                    face=border_face, 
                    color=border_color, 
                    edges_enable=edges_enable, 
                    edges_linewidths=edges_linewidths, 
                    draw_aabb=aabb_boxes_enable, 
                    label=faces_label_enable, 
                    alpha=border_faces_alpha, 
                    plane=faces_plane_enable, 
                    plane_size=faces_plane_size,
                    plane_alpha=faces_plane_alpha)
    
    ax.set_title(f"Mesh {mesh.title}")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()
    
if __name__ == '__main__':
    mesh = Mesh("examples/small_sphere_double.dat")
    #mesh = Mesh("examples/bunny_double.dat")
    bvh = BVHBuilder(mesh=mesh, eps=1e-12)
    bvh.prepare_mesh(esc_enable=False)
    bvh.build_tree(face_on_leaf=1, split_func="sah")
    bvh.traversal_tree()
    border_faces = [face[0] for face in bvh.f_fix.values()]
    intersection_segment = [segment for face in bvh.f_fix.values() for segment in face[1]]
    plot_mesh(mesh=mesh, 
              edges_enable=False, 
              faces_enable=True,
              faces_label_enable=False,
              border_enable=True, 
              border_color="pink", 
              border_faces=border_faces, 
              border_faces_alpha=0.3,
              intersection_segments_enable=True,
              intersection_segments=intersection_segment,
              intersection_segments_linewidths=4)
