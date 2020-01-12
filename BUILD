package(default_visibility = ["//visibility:public"])

load("@rules_python//python:defs.bzl", "py_binary")
load("@requirements//:requirements.bzl", "requirement")
load("@requirements_test//:requirements.bzl", test_requirement="requirement")
# bazel's pip implementation doesn't currently install transtive requirements
load("@requirements_transitive//:requirements.bzl", transitive_requirement="all_requirements")

py_library(
    name = "main",
    srcs = ["main.py"],
    srcs_version = "PY3",
    python_version = "PY3",
    data = ["data"],
    deps = [
	":dice_calculator",
        requirement("dialogflow"),
        requirement("absl-py")
    ],
)

py_library(
    name = "dice_calculator",
    srcs = ["dice_calculator.py"],
    srcs_version = "PY3",
    python_version = "PY3",
    data = ["data"],
    deps = [
        requirement("absl-py"),
        requirement("lark-parser")
    ],
)

py_test(
    name = "test_main",
    srcs = ["test_main.py"],
    srcs_version = "PY3",
    python_version = "PY3",
    deps = [
        ":main",
        ":dice_calculator"
    ]
)

py_test(
    name = "test_dice_calculator",
    srcs = ["test_dice_calculator.py"],
    srcs_version = "PY3",
    python_version = "PY3",
    deps = [":dice_calculator"]
)

py_test(
    name = "test_e2e",
    srcs = ["test_e2e.py"],
    srcs_version = "PY3",
    python_version = "PY3",
    deps = [
        ":main",
        test_requirement("flask"),
    ] + transitive_requirement,
)

py_test(
    name = "wrap_pytype",
    srcs = ["wrap_pytype.py"],
    deps = [
        ":main",
        test_requirement("pytype")
    ] + transitive_requirement,
)

filegroup(
    name = "data",
    srcs = glob(["data/*.json"])
)
