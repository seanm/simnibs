from abc import ABC, abstractmethod

import numpy as np
import numpy.typing as npt
from scipy.spatial.transform import Rotation

from simnibs.simulation.tms_coil.tcd_element import TcdElement


class TmsCoilDeformation(ABC, TcdElement):
    """Represents a deformation

    Parameters
    ----------
    initial : float
        The initial value of the deformation (e.g angle of a rotation deformation)
    range : tuple[float, float]
        The allowed range of the deformation

    Attributes
    ----------------------
    initial : float
        The initial value of the deformation (e.g angle of a rotation deformation)
    range : tuple[float, float]
        The allowed range of the deformation
    current : float
        The current value of the deformation
    """
    def __init__(self, initial: float, range: tuple[float, float]):
        self.initial = initial
        self._current = initial
        self.range = range

    def reset(self):
        self.current = self.initial

    @property
    def current(self) -> float:
        return self._current

    @current.setter
    def current(self, value):
        if self.current < self.range[0] or self.current > self.range[1]:
            raise ValueError(
                f"Value must be within the range ({self.range[0]}, {self.range[1]})"
            )
        else:
            self._current = value

    @abstractmethod
    def apply(self, points: npt.NDArray[np.float_]) -> npt.NDArray[np.float_]:
        """Applies the deformation to every point

        Parameters
        ----------
        points : npt.NDArray[np.float_] (Nx3)
            The points that should be deformed
        

        Returns
        -------
        npt.NDArray[np.float_] (Nx3)
            The deformed points
        """
        pass

    @abstractmethod
    def as_matrix(self) -> npt.NDArray[np.float_]:
        """A affine matrix representation of the deformation

        Returns
        -------
        npt.NDArray[np.float_] (4x4)
            The affine matrix representing the deformation
        """
        pass

    def to_tcd(self) -> dict:
        tcd_deformation = {}
        tcd_deformation["initial"] = self.initial
        tcd_deformation["range"] = list(self.range)
        return tcd_deformation

    @classmethod
    def from_tcd(cls, tcd_deformation: dict):
        initial = tcd_deformation["initial"]
        deform_range = tcd_deformation["range"]
        if tcd_deformation["type"] == "x":
            return TmsCoilTranslation(initial, deform_range, 0)
        elif tcd_deformation["type"] == "y":
            return TmsCoilTranslation(initial, deform_range, 1)
        elif tcd_deformation["type"] == "z":
            return TmsCoilTranslation(initial, deform_range, 2)
        elif tcd_deformation["type"] == "rot2p":
            point_1 = np.array(tcd_deformation["point1"])
            point_2 = np.array(tcd_deformation["point2"])
            return TmsCoilRotation(initial, deform_range, point_1, point_2)
        else:
            raise ValueError(f"Invalid deformation type: {tcd_deformation['type']}")


class TmsCoilTranslation(TmsCoilDeformation):
    """Represents a translation

    Parameters
    ----------
    initial : float
        The initial value of the deformation (e.g angle of a rotation deformation)
    range : tuple[float, float]
        The allowed range of the deformation
    axis : int
        The axis to be used for the translation

    Attributes
    ----------------------
    initial : float
        The initial value of the deformation (e.g angle of a rotation deformation)
    range : tuple[float, float]
        The allowed range of the deformation
    current : float
        The current value of the deformation
    axis : int
        The axis to be used for the translation
    """

    def __init__(
        self,
        initial: float,
        range: tuple[float, float],
        axis: int,
    ):
        super().__init__(initial, range)
        self.axis = axis

    def apply(self, points: npt.NDArray[np.float_]):
        return points + self.get_translation()

    def get_translation(self) -> npt.NDArray[np.float_]:
        """Returns the translation vector for this coil translation

        Returns
        -------
        npt.NDArray[np.float_] (3)
            The translation vector for this coil translation
        """
        translation = np.zeros(3)
        translation[self.axis] = self.current
        return translation

    def as_matrix(self) -> npt.NDArray[np.float_]:
        affine_matrix = np.eye(4)
        affine_matrix[:3, 3] = self.get_translation()
        return affine_matrix

    def to_tcd(self) -> dict:
        tcd_deformation = super().to_tcd()
        if self.axis == 0:
            tcd_deformation["type"] = "x"
        elif self.axis == 1:
            tcd_deformation["type"] = "y"
        elif self.axis == 2:
            tcd_deformation["type"] = "z"
        else:
            raise ValueError(f"Translation axis ({self.axis}) out of range (0-2)")
        return tcd_deformation


class TmsCoilRotation(TmsCoilDeformation):
    """Represents a rotation around an axis defined by two points

    Parameters
    ----------
    initial : float
        The initial value of the deformation (e.g angle of a rotation deformation)
    range : tuple[float, float]
        The allowed range of the deformation
    point_1: npt.NDArray[np.float_]
        The first point of the rotation axis
    point_2: npt.NDArray[np.float_]
        The second point of the rotation axis

    Attributes
    ----------------------
    initial : float
        The initial value of the deformation (e.g angle of a rotation deformation)
    range : tuple[float, float]
        The allowed range of the deformation
    current : float
        The current value of the deformation
    point_1: npt.NDArray[np.float_]
        The first point of the rotation axis
    point_2: npt.NDArray[np.float_]
        The second point of the rotation axis
    """

    def __init__(
        self,
        initial: float,
        range: tuple[float, float],
        point_1: npt.NDArray[np.float_],
        point_2: npt.NDArray[np.float_],
    ):
        super().__init__(initial, range)
        self.point_1 = point_1
        self.point_2 = point_2

    def get_rotation(self) -> npt.NDArray[np.float_]:
        """Returns the affine matrix of the rotation around the axis defined by the two points

        Returns
        -------
        npt.NDArray[np.float_] (4x4)
            The affine matrix representing the rotation around the axis defined by the two points
        """
        v = (self.point_2 - self.point_1) / np.linalg.norm(self.point_2 - self.point_1)
        T = np.identity(4)
        T[:3, 3] = self.point_1
        iT = np.identity(4)
        iT[:3, 3] = -self.point_1
        R = np.identity(4)
        R[:3, :3] = Rotation.from_rotvec(v * self.current, degrees=True).as_matrix()
        Q = T @ R @ iT
        return Q

    def apply(self, points: npt.NDArray[np.float_]):
        rotation_matrix = self.get_rotation()
        points = points @ rotation_matrix[:3, :3].T + rotation_matrix[None, :3, 3]
        return points

    def as_matrix(self) -> npt.NDArray[np.float_]:
        return self.get_rotation()

    def to_tcd(self) -> dict:
        tcd_deformation = super().to_tcd()
        tcd_deformation["type"] = "rot2p"
        tcd_deformation["point1"] = self.point_1.tolist()
        tcd_deformation["point2"] = self.point_2.tolist()
        return tcd_deformation
