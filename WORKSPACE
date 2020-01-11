
# Using unrelease version for pip3 support
# load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")
# http_archive(
#     name = "rules_python",
#     url = "https://github.com/bazelbuild/rules_python/releases/download/0.0.1/rules_python-0.0.1.tar.gz",
#     sha256 = "aa96a691d3a8177f3215b14b0edc9641787abaaa30363a080165d06ab65e1161",
# )

load("@bazel_tools//tools/build_defs/repo:git.bzl", "git_repository")
git_repository(
    name = "rules_python",
    remote = "https://github.com/bazelbuild/rules_python.git",
    commit = "94677401bc56ed5d756f50b441a6a5c7f735a6d4",
)


load("@rules_python//python:repositories.bzl", "py_repositories")
load("@rules_python//python:pip.bzl", "pip_repositories", "pip3_import")

py_repositories()
pip_repositories()

pip3_import(
    name = "requirements",
    requirements = "//:requirements.txt",
)
load("@requirements//:requirements.bzl", "pip_install")
pip_install()

pip3_import(
    name = "requirements_test",
    requirements = "//:requirements-test.txt",
)
load("@requirements_test//:requirements.bzl", pip_install_test="pip_install")
pip_install_test()

pip3_import(
    name = "requirements_transitive",
    requirements = "//:requirements-transitive.txt",
)
load("@requirements_transitive//:requirements.bzl", pip_install_transitive="pip_install")
pip_install_transitive()