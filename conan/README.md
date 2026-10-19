# bot2_calib Conan 依赖快照

本目录保存 bot2_calib 所需的固定依赖清单、配置、配方修订号及离线安装脚本. 大型二进制文件发布到 [GitHub Releases](https://github.com/qiqiblue/HALCON-calib/releases/tag/conan-deps-20261019), 不放进 Git 历史.

这不是 Conan HTTP remote, 不能将本目录的 GitHub URL 直接填进 `conan remote add`. 机器人下载归档后, 使用官方 `conan cache restore` 导入, 然后执行 `conan install --no-remote --build=never`. 安装过程不访问 pandatea Conan remote, 也不调用原来的 `conan_setup.sh`.

## 支持的平台

| profile | 系统 | 目标架构 | 编译器 | C++ / 构建类型 |
| --- | --- | --- | --- | --- |
| aarch22 | Ubuntu 22.04 | aarch64 / armv8 | Clang 14, libstdc++11 | C++17 / MinSizeRel |
| aarch24 | Ubuntu 24.04 | aarch64 / armv8 | Clang 18, libstdc++11 | C++17 / MinSizeRel |

两个平台分别保存二进制包, 不能混用. profiles 和 settings_user.yml 取自项目实际使用的 `conan-config/1.0.0#e1b2357b538558c3282c487086efb056`, 不虚构 L4T setting.

## 包含的依赖

每个平台有 **59个完整配方及28个所需二进制包**, 包括 host 依赖和 build tools. Conan 明确跳过的传递依赖只保留配方, 不额外下载不需要的二进制. 完整 recipe revision、package ID、package revision 见 [aarch22 清单](packages/aarch22-summary.json) 和 [aarch24 清单](packages/aarch24-summary.json); `packages/<profile>.json` 保存官方 Conan 包清单, `locks/` 保存 lockfile.

主要依赖:

| 分类 | 包和版本 |
| --- | --- |
| 界面和图节点 | qt/6.11.1, qtnodes/3.0.16 |
| 视觉和数学 | opencv/4.13.0, eigen/3.4.0, boost/1.91.0 |
| 项目与机器人 SDK | tea/1.1.1, abc/0.8.16, realman/1.1.1.t2, woosh/1.3.17 |
| 日志、配置和归档 | fmt/12.2.0, spdlog/1.17.0, cli/2.2.0, nlohmann_json/3.12.0, toml11/4.4.0, libzip/1.11.4 |
| 传递运行依赖 | zlib/1.3.2, bzip2/1.0.8, libbacktrace/cci.20210118, libunwind/8.0.1, xkbcommon/1.5.0 |
| 系统适配配方 | egl/system, opengl/system, xorg/system, xkeyboard-config/system |
| 构建工具 | cmake/4.4.0, ninja/1.13.2, pkgconf/2.5.1, meson/1.10.2 |

发现并处理的版本冲突: 私有源当前最新 ABC 配方 `573a95fc1bc67c2e56b073e9f4d0c979` 要求 RealMan 1.1.6, 与项目固定的 1.1.1.t2 冲突. 本快照锁定已发布且兼容的 `abc/0.8.16#a8e106b310820f4db56423971988b696`, 不通过升级或强制覆盖机械臂 SDK 消除冲突.

`consumer/` 仅保存生成依赖图所需的两份项目依赖声明. 原项目的相机、标定、运动和 UI 代码不在本仓库中修改. 原依赖声明的来源提交和 SHA-256 见 [snapshot.json](snapshot.json), 文本校验统一 LF 换行, 其余内容必须一致.

## 机器人安装

先按照 bot2_calib 项目 README 准备系统开发包、对应 Clang、HALCON 开发环境和许可证、RealSense SDK及设备规则. 这些内容不属于本 Conan 归档. EGL/OpenGL/X11 等 system 配方也不包含系统图形库, 系统开发包必须已安装.

### 1. 安装 Conan 2.30.0

已有匹配版本时直接使用, 包括原来的 `/opt/conan-venv/bin/conan`. 新环境可安装到独立 venv:

```bash
sudo apt-get install -y python3-venv
python3 -m venv "$HOME/.local/share/conan-bot2-2.30"
"$HOME/.local/share/conan-bot2-2.30/bin/python" -m pip install conan==2.30.0
export PATH="$HOME/.local/share/conan-bot2-2.30/bin:$PATH"
conan --version
```

这一步需要 Python 包安装源; 本仓库未打包 pip wheels. Conan 已安装时无需重复安装.

### 2. 获取固定版本的安装脚本和平台归档

```bash
mkdir -p /home/data/tea
cd /home/data/tea
git clone --depth 1 --filter=blob:none --sparse --branch conan-deps-20261019 \
  https://github.com/qiqiblue/HALCON-calib.git HALCON-calib-deps
cd HALCON-calib-deps
git sparse-checkout set conan

# Ubuntu 22.04 使用 aarch22; Ubuntu 24.04 将这里改成 aarch24.
profile=aarch22
mkdir -p assets
release=https://github.com/qiqiblue/HALCON-calib/releases/download/conan-deps-20261019
curl -fL --retry 3 -o "assets/bot2-calib-${profile}-conan.tgz" \
  "$release/bot2-calib-${profile}-conan.tgz"
curl -fL --retry 3 -o "assets/${profile}.manifest.json" \
  "$release/${profile}.manifest.json"
curl -fL --retry 3 -o "assets/${profile}.sha256" \
  "$release/${profile}.sha256"
(cd assets && sha256sum -c "${profile}.sha256")
```

完全离线时, 在联网电脑下载对应发布标签下的 `conan/` 和以上三个资产, 一起复制到机器人. 不混用 main 上较新的脚本与旧归档.

### 3. 恢复依赖并部署运行库

停止正在运行的标定软件, 备份现场 `bin/bot2_calib/config/` 和 `data/`. 以下源码路径替换为实际工作目录.

```bash
cd /home/data/tea/HALCON-calib-deps

# 使用单独缓存, 无需更改原来 /opt/conan 的权限和数据.
export CONAN_HOME="$HOME/.cache/bot2-calib-conan"
python3 conan/bundle.py install \
  --source /home/data/tea/experiments/bot2_calib_main_build \
  --assets assets
```

脚本自动核对 Ubuntu 版本、aarch64 架构、Conan 版本、源项目依赖声明、平台清单和归档 SHA-256. 核对失败时拒绝导入. 不删除旧 build/cache、相机配置或标定数据. `config install` 仅安装本目录的两个 profiles 和自定义 settings, 不复制账号、Token、认证数据库或整个 `/opt/conan`.

随后使用 Conan 官方恢复和完整性检查, 通过 `--no-remote --build=never` 为实际项目生成 `.cache/conan/`、CMake Presets, 并用项目原有 deployer 部署 `bin/bot2_calib/lib/` 和 Qt 插件. 系统包使用检查模式, 缺失时明确失败, 不自动执行联网 APT.

### 4. 编译和后续增量编译

```bash
cd /home/data/tea/experiments/bot2_calib_main_build
source /opt/MVTec/HALCON-26.05-Progress/.profile_halcon

# 首次迁移依赖或首次生成构建目录, 需要重新配置.
CMAKE_BUILD_PARALLEL_LEVEL=2 python3 share/py/build_app.py \
  bot2_calib local-test bot2_calib WITH_BOT2_CALIB --no-package
python3 share/py/generate_run.py bot2_calib

# 后续只修改 C++/UI, 且 .cache/build/CMakeCache.txt 已存在时:
CMAKE_BUILD_PARALLEL_LEVEL=2 python3 share/py/build_app.py \
  bot2_calib local-test bot2_calib WITH_BOT2_CALIB --skip-configure --no-package
```

使用此快照后, 不再执行原 `share/sh/conan_setup.sh`, 否则它仍会重新访问 pandatea 并清理现有生成目录. 发布包、启动和硬件验证继续按原项目文档执行.

## 生成和发布方式

GitHub Actions 的 [Conan 归档工作流](../.github/workflows/conan-mirror.yml) 可手动启动. 它在两个 Ubuntu Linux runner 上分别下载目标 ARM64 包, 使用 Conan 官方 `cache save` 归档, 在全新的缓存中恢复, 检查完整性和离线依赖图. 无需执行 ARM64 程序即可验证包闭包; 这不能代替 ARM64 C++ 编译和机器人运行验证.

两个平台均通过后才发布 Release. 下载或校验失败不会发布成功版本. 日常机器人安装不依赖私有 Conan 源; 维护者重新生成归档时仍需要访问原始上游. 所有上游包保留其原有许可证和包内声明. 不加入 HALCON 许可证、GitHub/Conan 凭据或机器人配置数据.

本次验证状态以 Release 中两个 `*.manifest.json` 的 validation 字段和对应 Actions 执行结果为准. 不将静态清单检查称为目标编译或硬件通过.
