"""
Core smoothing routines that operate on 2D arrays.
"""
import enum

from abc import ABC
from dataclasses import dataclass
from typing import Any, Dict

from .gpu_compat import ArrayType, get_array_module


# not married to the term "Cartesian"
GridType = enum.Enum(
    "GridType", ["CARTESIAN", "CARTESIAN_WITH_LAND", "IRREGULAR_CARTESIAN_WITH_LAND", "POP_TRIPOLAR_GRID"]
)

ALL_KERNELS = {}  # type: Dict[GridType, Any]


@dataclass
class BaseLaplacian(ABC):
    def __call__(self, field):
        pass  # pragma: no cover

    # change to property when we are using python 3.9
    # https://stackoverflow.com/questions/128573/using-property-on-classmethods
    @classmethod
    def required_grid_args(self):
        try:
            return list(self.__annotations__)
        except AttributeError:
            return []


@dataclass
class CartesianLaplacian(BaseLaplacian):
    """̵Laplacian for regularly spaced Cartesian grids."""

    def __call__(self, field: ArrayType):
        np = get_array_module(field)
        return (
            -4 * field
            + np.roll(field, -1, axis=-1)
            + np.roll(field, 1, axis=-1)
            + np.roll(field, -1, axis=-2)
            + np.roll(field, 1, axis=-2)
        )


ALL_KERNELS[GridType.CARTESIAN] = CartesianLaplacian


@dataclass
class CartesianLaplacianWithLandMask(BaseLaplacian):
    """̵Laplacian for regularly spaced Cartesian grids with land mask.

    Attributes
    ----------
    wet_mask: Mask array, 1 for ocean, 0 for land
    """

    wet_mask: ArrayType

    def __post_init__(self):
        np = get_array_module(self.wet_mask)

        self.wet_fac = (
            np.roll(self.wet_mask, -1, axis=-1)
            + np.roll(self.wet_mask, 1, axis=-1)
            + np.roll(self.wet_mask, -1, axis=-2)
            + np.roll(self.wet_mask, 1, axis=-2)
        )

    def __call__(self, field: ArrayType):
        np = get_array_module(field)

        out = np.nan_to_num(field)  # set all nans to zero
        out = self.wet_mask * out

        out = (
            -self.wet_fac * out
            + np.roll(out, -1, axis=-1)
            + np.roll(out, 1, axis=-1)
            + np.roll(out, -1, axis=-2)
            + np.roll(out, 1, axis=-2)
        )

        out = self.wet_mask * out
        return out


ALL_KERNELS[GridType.CARTESIAN_WITH_LAND] = CartesianLaplacianWithLandMask


@dataclass
<<<<<<< HEAD
class IrregularCartesianLaplacianWithLandMask(BaseLaplacian):
    """̵Laplacian for irregularly spaced Cartesian grids with land mask.
    
    Attributes
    ----------
    wet_mask: Mask array, 1 for ocean, 0 for land
    dxw: x-spacing centered at western cell edge
    dyw: y-spacing centered at western cell edge
    dxs: x-spacing centered at southern cell edge
    dys: y-spacing centered at southern cell edge
    area: cell area
    """

    wet_mask: ArrayType
    dxw: ArrayType
    dyw: ArrayType
    dxs: ArrayType
    dys: ArrayType
    area: ArrayType

    def __post_init__(self):
        np = get_array_module(self.wet_mask)
        
        self.w_wet_mask = self.wet_mask * np.roll(self.wet_mask, -1, axis=-1)
        self.s_wet_mask = self.wet_mask * np.roll(self.wet_mask, -1, axis=-2)

    def __call__(self, field: ArrayType):
        np = get_array_module(field)

        out = np.nan_to_num(field)

        wflux = (
            (out - np.roll(out, -1, axis=-1)) / self.dxw * self.dyw
        )  # flux across western cell edge
        sflux = (
            (out - np.roll(out, -1, axis=-2)) / self.dys * self.dxs
        )  # flux across southern cell edge

        wflux = wflux * self.w_wet_mask  # no-flux boundary condition
        sflux = sflux * self.s_wet_mask  # no-flux boundary condition

        out = np.roll(wflux, 1, axis=-1) - wflux + np.roll(sflux, 1, axis=-2) - sflux

        out = out / self.area
        return out


ALL_KERNELS[
    GridType.IRREGULAR_CARTESIAN_WITH_LAND
] = IrregularCartesianLaplacianWithLandMask


class POPTripolarSimpleLaplacian(CartesianLaplacianWithLandMask):
    """̵Laplacian for POP tripolar grid geometry with land mask, but assuming that dx = dy = 1

    Attributes
    ----------
    wet_mask: Mask array, 1 for ocean, 0 for land
    """

    wet_mask: ArrayType

    def __post_init__(self):
        np = get_array_module(self.wet_mask)

        nbdry = self.wet_mask[..., [-1], :]  # grab northernmost row
        nbdry_flipped = nbdry[..., ::-1]  # mirror it
        wet_mask_extended = np.concatenate(
            (self.wet_mask, nbdry_flipped), axis=-2
        )  # append it

        self.wet_fac_extended = (
            np.roll(wet_mask_extended, -1, axis=-1)
            + np.roll(wet_mask_extended, 1, axis=-1)
            + np.roll(wet_mask_extended, -1, axis=-2)
            + np.roll(wet_mask_extended, 1, axis=-2)
        )

    def __call__(self, field: ArrayType):
        np = get_array_module(field)

        data = np.nan_to_num(field)  # set all nans to zero
        data = self.wet_mask * data

        nbdry = data[..., [-1], :]  # grab northernmost row
        nbdry_flipped = nbdry[..., ::-1]  # mirror it
        data_extended = np.concatenate((data, nbdry_flipped), axis=-2)  # append it

        out = (
            -self.wet_fac_extended * data_extended
            + np.roll(data_extended, -1, axis=-1)
            + np.roll(data_extended, 1, axis=-1)
            + np.roll(data_extended, -1, axis=-2)
            + np.roll(data_extended, 1, axis=-2)
        )

        out = out[..., 0:-1, :]  # disregard appended row

        out = self.wet_mask * out
        return out


ALL_KERNELS[GridType.POP_TRIPOLAR_GRID] = POPTripolarSimpleLaplacian


def required_grid_vars(grid_type: GridType):
    """Utility function for figuring out the required grid variables
    needed by each grid type.

    Parameters
    ----------
    grid_type : GridType
        The grid type

    Returns
    -------
    grid_vars : list
        A list of names of required grid variables.
    """

    laplacian = ALL_KERNELS[grid_type]
    return laplacian.required_grid_args()
