"""Noise filter"""

import numpy as np

from ..abstract_processor import AbstractProcessor
from ..utils.interpolation import FastGridInterpolator
from ..region_growing.label_connected_comp import LabelConnectedComp
from ..utils.labels import Labels


class NoiseFilter(AbstractProcessor):
    """
    Noise filter based on elevation level and cluster size. Any points below
    ground level, and points that are within clusters with a size below the
    given threshold, will be labelled as noise.

    Parameters
    ----------
    label : int
        Class label to use for this fuser.
    ahn_reader : AHNReader object
        Elevation data reader.
    epsilon : float (default: 0.2)
        Precision of the fuser.
    octree_level : int (default: 9)
        Octree level for clustering connected components.
    min_component_size : int (default: 100)
        Minimum size of a cluster below which it is regarded as noise.
    """
    def __init__(self, label, ahn_reader, epsilon=0.2, octree_level=9,
                 min_component_size=100):
        super().__init__(label)

        self.ahn_reader = ahn_reader
        self.epsilon = epsilon
        self.octree_level = octree_level
        self.min_component_size = min_component_size

    def get_label_mask(self, points, labels, mask, tilecode):
        """
        Returns the label mask for the given pointcloud.

        Parameters
        ----------
        points : array of shape (n_points, 3)
            The point cloud <x, y, z>.
        labels : array of shape (n_points,)
            Ignored by this fuser.
        mask : array of shape (n_points,) with dtype=bool
            Pre-mask used to label only a subset of the points.
        tilecode : str
            The CycloMedia tile-code for the given pointcloud.

        Returns
        -------
        An array of shape (n_points,) with dtype=bool indicating which points
        should be labelled according to this fuser.
        """
        # Create lcc object and perform lcc
        lcc = LabelConnectedComp(self.label, octree_level=self.octree_level,
                                 min_component_size=self.min_component_size)
        point_components = lcc.get_components(points[mask])

        cc_labels, counts = np.unique(point_components,
                                      return_counts=True)

        cc_labels_filtered = cc_labels[counts < self.min_component_size]

        # Get the interpolated ground points of the tile
        ahn_tile = self.ahn_reader.filter_tile(tilecode)
        surface = ahn_tile['ground_surface']
        fast_z = FastGridInterpolator(ahn_tile['x'], ahn_tile['y'], surface)
        target_z = fast_z(points[mask, :])

        label_mask = np.zeros((len(points),), dtype=bool)
        # Label points below ground and points in small components.
        label_mask[mask] = (np.in1d(point_components, cc_labels_filtered)
                            | ((points[mask, 2] - target_z) < -self.epsilon))

        print(f'Noise filter => processed '
              f'(label={self.label}, {Labels.get_str(self.label)}).')

        return label_mask