from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set

from PIL.Image import Image as ImageType

from custom_components.xiaomi_cloud_map_extractor.const import *
from custom_components.xiaomi_cloud_map_extractor.types import CalibrationPoints, ImageConfig


class Point:
    def __init__(self, x: float, y: float, a=None):
        self.x = x
        self.y = y
        self.a = a

    def __str__(self) -> str:
        if self.a is None:
            return f"({self.x}, {self.y})"
        return f"({self.x}, {self.y}, a = {self.a})"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: Point) -> bool:
        return other is not None and self.x == other.x and self.y == other.y and self.a == other.a

    def as_dict(self) -> Dict[str, Any]:
        if self.a is None:
            return {
                ATTR_X: self.x,
                ATTR_Y: self.y
            }
        return {
            ATTR_X: self.x,
            ATTR_Y: self.y,
            ATTR_A: self.a
        }

    def to_img(self, image_dimensions) -> Point:
        return image_dimensions.to_img(self)

    def rotated(self, image_dimensions) -> Point:
        alpha = image_dimensions.rotation
        w = int(image_dimensions.width * image_dimensions.scale)
        h = int(image_dimensions.height * image_dimensions.scale)
        x = self.x
        y = self.y
        while alpha > 0:
            tmp = y
            y = w - x
            x = tmp
            tmp = h
            h = w
            w = tmp
            alpha = alpha - 90
        return Point(x, y)

    def __mul__(self, other) -> Point:
        return Point(self.x * other, self.y * other, self.a)

    def __truediv__(self, other) -> Point:
        return Point(self.x / other, self.y / other, self.a)


class Obstacle(Point):
    def __init__(self, x: float, y: float, details: Dict[str, Any]):
        super().__init__(x, y)
        self.details = details

    def as_dict(self) -> Dict[str, Any]:
        return {**super(Obstacle, self).as_dict(), **self.details}

    def __str__(self) -> str:
        return f"({self.x}, {self.y}, details = {self.details})"


class ImageDimensions:
    def __init__(self, top: int, left: int, height: int, width: int, scale: float, rotation: int,
                 img_transformation: Callable[[Point], Point]):
        self.top = top
        self.left = left
        self.height = height
        self.width = width
        self.scale = scale
        self.rotation = rotation
        self.img_transformation = img_transformation

    def to_img(self, point: Point) -> Point:
        p = self.img_transformation(point)
        return Point((p.x - self.left) * self.scale, (self.height - (p.y - self.top) - 1) * self.scale)


class ImageData:
    def __init__(self, size: int, top: int, left: int, height: int, width: int, image_config: ImageConfig,
                 data: ImageType, img_transformation: Callable[[Point], Point], additional_layers: dict = None):
        trim_left = int(image_config[CONF_TRIM][CONF_LEFT] * width / 100)
        trim_right = int(image_config[CONF_TRIM][CONF_RIGHT] * width / 100)
        trim_top = int(image_config[CONF_TRIM][CONF_TOP] * height / 100)
        trim_bottom = int(image_config[CONF_TRIM][CONF_BOTTOM] * height / 100)
        scale = image_config[CONF_SCALE]
        rotation = image_config[CONF_ROTATE]
        self.size = size
        self.dimensions = ImageDimensions(top + trim_bottom,
                                          left + trim_left,
                                          height - trim_top - trim_bottom,
                                          width - trim_left - trim_right,
                                          scale,
                                          rotation, img_transformation)
        self.is_empty = height == 0 or width == 0
        self.data = data
        if additional_layers is None:
            self.additional_layers = {}
        else:
            self.additional_layers = dict(filter(lambda l: l[1] is not None, additional_layers.items()))

    def as_dict(self) -> Dict[str, Any]:
        return {
            ATTR_SIZE: self.size,
            ATTR_OFFSET_Y: self.dimensions.top,
            ATTR_OFFSET_X: self.dimensions.left,
            ATTR_HEIGHT: self.dimensions.height,
            ATTR_SCALE: self.dimensions.scale,
            ATTR_ROTATION: self.dimensions.rotation,
            ATTR_WIDTH: self.dimensions.width
        }

    @staticmethod
    def create_empty(data: ImageType) -> ImageData:
        image_config = {
            CONF_TRIM: {
                CONF_LEFT: 0,
                CONF_RIGHT: 0,
                CONF_TOP: 0,
                CONF_BOTTOM: 0
            },
            CONF_SCALE: 1,
            CONF_ROTATE: 0
        }
        return ImageData(0, 0, 0, 0, 0, image_config, data, lambda p: p)


class Path:
    def __init__(self, point_length: Optional[int], point_size: Optional[int], angle: Optional[int],
                 path: List[List[Point]]):
        self.point_length = point_length
        self.point_size = point_size
        self.angle = angle
        self.path = path

    def as_dict(self) -> Dict[str, Any]:
        return {
            ATTR_POINT_LENGTH: self.point_length,
            ATTR_POINT_SIZE: self.point_size,
            ATTR_ANGLE: self.angle,
            ATTR_PATH: self.path
        }


class Zone:
    def __init__(self, x0: float, y0: float, x1: float, y1: float):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    def __str__(self) -> str:
        return f"[{self.x0}, {self.y0}, {self.x1}, {self.y1}]"

    def __repr__(self) -> str:
        return self.__str__()

    def as_dict(self) -> Dict[str, Any]:
        return {
            ATTR_X0: self.x0,
            ATTR_Y0: self.y0,
            ATTR_X1: self.x1,
            ATTR_Y1: self.y1
        }

    def as_area(self) -> Area:
        return Area(self.x0, self.y0, self.x0, self.y1, self.x1, self.y1, self.x1, self.y0)


class Room(Zone):
    def __init__(self, number: int, x0: Optional[float], y0: Optional[float], x1: Optional[float], y1: Optional[float],
                 name: str = None, pos_x: float = None, pos_y: float = None):
        super().__init__(x0, y0, x1, y1)
        self.number = number
        self.name = name
        self.pos_x = pos_x
        self.pos_y = pos_y

    def as_dict(self) -> Dict[str, Any]:
        super_dict = {**super(Room, self).as_dict()}
        if self.name is not None:
            super_dict[ATTR_NAME] = self.name
        if self.pos_x is not None:
            super_dict[ATTR_X] = self.pos_x
        if self.pos_y is not None:
            super_dict[ATTR_Y] = self.pos_y
        return super_dict

    def __str__(self) -> str:
        return f"[number: {self.number}, name: {self.name}, {self.x0}, {self.y0}, {self.x1}, {self.y1}]"

    def __repr__(self) -> str:
        return self.__str__()

    def point(self) -> Optional[Point]:
        if self.pos_x is not None and self.pos_y is not None and self.name is not None:
            return Point(self.pos_x, self.pos_y)
        return None


class Wall:
    def __init__(self, x0: float, y0: float, x1: float, y1: float):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    def __str__(self) -> str:
        return f"[{self.x0}, {self.y0}, {self.x1}, {self.y1}]"

    def __repr__(self) -> str:
        return self.__str__()

    def as_dict(self) -> Dict[str, Any]:
        return {
            ATTR_X0: self.x0,
            ATTR_Y0: self.y0,
            ATTR_X1: self.x1,
            ATTR_Y1: self.y1
        }

    def to_img(self, image_dimensions) -> Wall:
        p0 = Point(self.x0, self.y0).to_img(image_dimensions)
        p1 = Point(self.x1, self.y1).to_img(image_dimensions)
        return Wall(p0.x, p0.y, p1.x, p1.y)

    def as_list(self) -> List[float]:
        return [self.x0, self.y0, self.x1, self.y1]


class Area:
    def __init__(self, x0: float, y0: float, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.x3 = x3
        self.y3 = y3

    def __str__(self) -> str:
        return f"[{self.x0}, {self.y0}, {self.x1}, {self.y1}, {self.x2}, {self.y2}, {self.x3}, {self.y3}]"

    def __repr__(self) -> str:
        return self.__str__()

    def as_dict(self) -> Dict[str, Any]:
        return {
            ATTR_X0: self.x0,
            ATTR_Y0: self.y0,
            ATTR_X1: self.x1,
            ATTR_Y1: self.y1,
            ATTR_X2: self.x2,
            ATTR_Y2: self.y2,
            ATTR_X3: self.x3,
            ATTR_Y3: self.y3
        }

    def as_list(self) -> List[float]:
        return [self.x0, self.y0, self.x1, self.y1, self.x2, self.y2, self.x3, self.y3]

    def to_img(self, image_dimensions) -> Area:
        p0 = Point(self.x0, self.y0).to_img(image_dimensions)
        p1 = Point(self.x1, self.y1).to_img(image_dimensions)
        p2 = Point(self.x2, self.y2).to_img(image_dimensions)
        p3 = Point(self.x3, self.y3).to_img(image_dimensions)
        return Area(p0.x, p0.y, p1.x, p1.y, p2.x, p2.y, p3.x, p3.y)


class MapData:
    def __init__(self, calibration_center: float = 0, calibration_diff: float = 0):
        self._calibration_center = calibration_center
        self._calibration_diff = calibration_diff
        self.blocks = None
        self.charger: Optional[Point] = None
        self.goto: Optional[List[Point]] = None
        self.goto_path: Optional[Path] = None
        self.image: Optional[ImageData] = None
        self.no_go_areas: Optional[List[Area]] = None
        self.no_mopping_areas: Optional[List[Area]] = None
        self.no_carpet_areas: Optional[List[Area]] = None
        self.carpet_map: Optional[Set[int]] = []
        self.obstacles: Optional[List[Obstacle]] = None
        self.ignored_obstacles: Optional[List[Obstacle]] = None
        self.obstacles_with_photo: Optional[List[Obstacle]] = None
        self.ignored_obstacles_with_photo: Optional[List[Obstacle]] = None
        self.path: Optional[Path] = None
        self.predicted_path: Optional[Path] = None
        self.mop_path: Optional[Path] = None
        self.rooms: Optional[Dict[int, Room]] = None
        self.vacuum_position: Optional[Point] = None
        self.vacuum_room: Optional[int] = None
        self.vacuum_room_name: Optional[str] = None
        self.walls: Optional[List[Wall]] = None
        self.zones: Optional[List[Zone]] = None
        self.cleaned_rooms: Optional[Set[int]] = None
        self.map_name: Optional[str] = None

    def calibration(self) -> Optional[CalibrationPoints]:
        if self.image.is_empty:
            return None
        calibration_points = []
        for point in [Point(self._calibration_center, self._calibration_center),
                      Point(self._calibration_center + self._calibration_diff, self._calibration_center),
                      Point(self._calibration_center, self._calibration_center + self._calibration_diff)]:
            img_point = point.to_img(self.image.dimensions).rotated(self.image.dimensions)
            calibration_points.append({
                "vacuum": {"x": point.x, "y": point.y},
                "map": {"x": int(img_point.x), "y": int(img_point.y)}
            })
        return calibration_points
