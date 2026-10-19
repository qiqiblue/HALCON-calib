from conan import ConanFile


class AbTeaConanBase(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv"

    default_options = {
        "fmt/*:shared": True,
        "spdlog/*:shared": True,
        "protobuf/*:shared": True,
        "grpc/*:shared": True,
        "libzip/*:shared": True,
        "tea/*:shared": True,
        "boost/*:header_only": False,
        "boost/*:shared": False,
        "qt/*:shared": True,
        "qt/*:gui": True,
        "qt/*:widgets": True,
        "qt/*:opengl": "desktop",
        "qt/*:with_odbc": False,
        "qt/*:with_pq": False,
        "qt/*:with_sqlite3": False,
        "qt/*:qtcharts": True,
        "qt/*:qtdeclarative": True,
        "qt/*:qtgraphs": True,
        "qt/*:qtquick3d": True,
        "qt/*:qtshadertools": True,
        "opencv/*:shared": True,
        "opencv/*:calib3d": True,
        "opencv/*:dnn": False,
        "opencv/*:features2d": True,
        "opencv/*:flann": True,
        "opencv/*:gapi": False,
        "opencv/*:highgui": False,
        "opencv/*:imgcodecs": True,
        "opencv/*:imgproc": True,
        "opencv/*:ml": True,
        "opencv/*:objdetect": True,
        "opencv/*:photo": True,
        "opencv/*:stitching": False,
        "opencv/*:video": False,
        "opencv/*:videoio": False,
        "opencv/*:with_eigen": False,
        "opencv/*:with_jpeg2000": False,
        "opencv/*:with_openexr": False,
        "opencv/*:with_quirc": False,
        "opencv/*:with_tiff": False,
        "opencv/*:with_webp": False,
    }

    def layout(self):
        self.folders.build = ".cache/build"
        self.folders.generators = ".cache/conan"

    def common_requirements(self):
        self.requires("cli/2.2.0")
        self.requires("fmt/12.2.0", override=True)
        self.requires("spdlog/1.17.0")
        self.requires("tea/1.1.1")
        self.requires("boost/1.91.0")
        self.requires("qt/6.11.1")
        self.requires("opencv/4.13.0")

    def build_requirements(self):
        self.tool_requires("cmake/4.4.0")
        self.tool_requires("ninja/1.13.2")
