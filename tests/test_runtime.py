import unittest

from illustrious.runtime import check_driver_compatibility


class DriverCompatibilityTests(unittest.TestCase):
    def test_reported_cuda13_on_cuda124_failure(self):
        with self.assertRaisesRegex(RuntimeError, "illustrious:cuda12"):
            check_driver_compatibility("13.0", 12040)

    def test_cuda12_minor_compatibility_and_newer_drivers(self):
        for runtime, driver in (("12.8", 12040), ("12.8", 13000), ("13.0", 13000)):
            with self.subTest(runtime=runtime, driver=driver):
                check_driver_compatibility(runtime, driver)

    def test_unknown_driver_defers_to_real_cuda_initialization(self):
        check_driver_compatibility("12.8", None)
        check_driver_compatibility(None, 12040)

    def test_cuda11_host_is_not_directed_to_cuda12_image(self):
        with self.assertRaises(RuntimeError) as error:
            check_driver_compatibility("12.8", 11080)
        self.assertNotIn("illustrious:cuda12", str(error.exception))
