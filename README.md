## **Коротко о репозитории:**

Репа с готовыми моделями EdgePoint2 для запуска на OrangePi через tflite delegate с ускорителем ArmNN. Также здесь находятся скрипты для конвертации модели и инференса.
Оригинальная модель EdgePoint2 была переведена в формат tflite засчет изменений архитектуры, которые Вы можете увидеть сами. 

## **Сравнение с оригинальной моделью:**
Получилось достичь инференса модели с минимальными (незначительными) отличиями по сравнению с оригинальной моделью. Скорость инференса стала заметно выше, а нагрузка на CPU кратно снизилась. FPS вырос примерно в два раза.

#### Отклонение значений дескрипторов по сравнению с оригинальной моделью колеблется в пределах 0.01

**Нагрузка при инференсе оригинальной модели:**

<img width="653" height="255" alt="image" src="https://github.com/user-attachments/assets/15cd0ba1-cb78-4e20-b720-280f43742996" />

**Нагрузка при инференсе модели через tflite delegate с ускорителем ArmNN:**

<img width="658" height="251" alt="image" src="https://github.com/user-attachments/assets/c8139617-9261-492b-b8b9-78d3f11190ca" />

**Оригинальная модель PyTorch:**

<img width="1655" height="690" alt="image" src="https://github.com/user-attachments/assets/114a94a0-18cc-464b-9650-c372ca38cbc0" />

**Модель tflite:**

<img width="1661" height="678" alt="image" src="https://github.com/user-attachments/assets/13896fa1-7040-492f-8229-7a39ba9d2513" />


##### **Установка (Docker)**

Все собиралось и запускалось с установленным Python 3.10



Создание виртуального окружения:


```
python -m venv env

source env/bin/activate
```


Установка необходимых зависимостей:


```
pip install tflite-runtime \
numpy \
matplotlib \
opencv-python \
torch \
torchvision \
onnx \
onnxruntime \
tensorflow \
flatbuffers
```


Необходимо собрать образ докер ArmNN:


```
cd armnn/build-tool

docker build \
--build-arg SETUP_ARGS="--target-arch=aarch64 --tflite-classic-delegate" \
--build-arg BUILD_ARGS="--target-arch=aarch64 --tflite-classic-delegate --neon-backend --cl-backend" \
--tag armnn:aarch64 \
--file docker/Dockerfile .
```


Далее необходимо копировать сборку на хост:


```
./scripts/docker-copy-to-host.sh armnn:aarch64 armnn_aarch64_build.tar.gz

cd docker_output
# Extract the tarball into a directory called _build
# If --debug is enabled, the extracted build directory will be called _build_debug tar -xzf armnn_aarch64_build.tar.gz

cd aarch64_build
# Set LD_LIBRARY_PATH to the current aarch64_build directory (.)
export LD_LIBRARY_PATH=.; ./UnitTests

# If the Arm NN TF Lite Delegate is built, we can also run DelegateUnitTests
cd delegate

# Set LD_LIBRARY_PATH to the current delegate directory (.) and the aarch64_build directory (..)
export LD_LIBRARY_PATH=.:..; ./DelegateUnitTests
```


Готово, ArmNN собран. Подробнее этот шаг описан ниже. 



##### **Подробнее (пропустить, если все собралось корректно)**

Ниже описаны docker build аргументы, которые можно использовать для настройки сборки Arm NN. Аргументы сборки Docker, такие как SETUP\_ARGS и BUILD\_ARGS, предоставляются в docker build в виде --build-arg.



SETUP_ARGS ( НАСТРОЙКИ )

Эти аргументы в конечном итоге передаются в setup-armnn.sh который загружает и собирает зависимости Arm NN. Для удобства использования (но при более длительной первоначальной сборке Docker) используйте --all чтобы все зависимости Arm NN были доступны для использования при сборке Arm NN. При повторной сборке Docker с использованием того же SETUP\_ARGS процесс настройки будет пропущен (с использованием кэширования предыдущих этапов сборки Docker). Строка SETUP\_ARGS должна начинаться и заканчиваться двойными кавычками ".




SETUP_ARGS | Description
|--|--|
--tflite-classic-delegate | flag: setup dependencies for the existing Arm NN TF Lite Delegate|
--tflite-opaque-delegate | flag: setup dependencies for the new Arm NN Opaque Delegate|
--tflite-parser | flag: setup dependencies for the Arm NN TF Lite Parser|
--onnx-parser | flag: setup dependencies for the Arm NN ONNX parser|
--all | flag: setup dependencies for all Arm NN components listed above|
--target-arch= | mandatory option: specify a target architecture aarch64, x86\_64, android64


Необходимо предоставить хотя бы один компонент (например, --tflite-classic-delegate) или иначе предоставьте --all для настройки зависимостей для всех компонентов.


Настройка для aarch64 со всеми зависимостями Arm NN:

```
SETUP_ARGS="--target-arch=aarch64 --all"
```


Настройка для aarch64 с использованием только существующих зависимостей TF Lite Delegate и TF Lite Parser:
```
SETUP_ARGS="--target-arch=aarch64 --tflite-classic-delegate --tflite-parser"
```




BUILD_ARGS

Следующие аргументы передаются в build-armnn.sh и определяют, какие компоненты Arm NN следует включить в сборку. Строка BUILD_ARGS должна начинаться и заканчиваться двойными кавычками ".



BUILD_ARGS | Description
|--|--|
--tflite-classic-delegate | flag: build the existing Arm NN TF Lite Delegate component|
--tflite-opaque-delegate | flag: build the new Arm NN Opaque Delegate|
--tflite-parser | flag: build the Arm NN TF Lite Parser component|
--onnx-parser | flag: build the Arm NN ONNX parser component|
--all | flag: build all Arm NN components listed above|
--target-arch= | mandatory option: specify a target architecture aarch64, x86\_64, android64|
--neon-backend | flag: build Arm NN with the NEON backend (CPU acceleration from ACL)|
--cl-backend | flag: build Arm NN with the OpenCL backend (GPU acceleration from ACL)|
--ref-backend | flag: build Arm NN with the reference backend. Should be used for verification purposes only. Does not provide any performance acceleration.|
--debug | flag: build Arm NN (and ACL) with debug turned on (optional: defaults to off)|
--clean | flag: remove previous Arm NN and ACL build prior to script execution (optional: defaults to off)|
--symlink-armnn | flag: instead of cloning, make a symbolic link from the armnn directory containing the build-tool to the source directory|
--armnn-cmake-args= | option: provide additional comma-separated CMake arguments string for building Arm NN (optional). String should start and end with single quotes '. Please refer to armnn/cmake/GlobalConfig.cmake|
--acl-scons-params= | option: provide additional comma-separated scons parameters string for building ACL 				(optional). String should start and end with single quotes '. ACL provide documentation for their build options


Необходимо предоставить хотя бы один компонент (т. е. --tflite-classic-delegate, --tflite-opaque-delegate, --tflite-parser, --onnx-parser) или указать --all

Компонент, указанный в BUILD_ARGS, также должен быть указан в SETUP_ARGS ранее, иначе сборка Arm NN завершится ошибкой.

Необходимо выбрать хотя бы один бэкенд (то есть --neon-backend, --cl-backend, --ref-backend).



Примеры:

Сборка для aarch64 со всеми компонентами Arm NN, с поддержкой NEON и OpenCL:
```
BUILD_ARGS="--target-arch=aarch64 --all --neon-backend --cl-backend"
```


Сборка для aarch64 с использованием существующего делегата Arm NN TF Lite, с поддержкой OpenCL и дополнительными параметрами scons для ACL:
```
BUILD_ARGS="--target-arch=aarch64 --tflite-classic-delegate --cl-backend --acl-scons-params='compress_kernels=1,benchmark_examples=1'"
```


Настройка для aarch64 со всеми зависимостями Arm NN, включенным OpenCL и дополнительными аргументами cmake для Arm NN:
```
BUILD_ARGS="--target-arch=aarch64 --all --cl-backend --armnn-cmake-args='-DBUILD_SAMPLE_APP=1,-DBUILD_UNIT_TESTS=0'"
```


Пример действительной комбинации SETUP_ARGS и BUILD_ARGS:


```
SETUP_ARGS="--target-arch=aarch64 --all"
BUILD_ARGS="--target-arch=aarch64 --tflite-classic-delegate --neon-backend --cl-backend"
```
Пример некорректного сочетания SETUP_ARGS и BUILD_ARGS:


```
SETUP_ARGS="--target-arch=aarch64 --tflite-classic-delegate"
BUILD_ARGS="--target-arch=aarch64 --all --neon-backend --cl-backend"
```
Приведенный выше пример некорректен, поскольку в нем выполняется попытка собрать все компоненты Arm NN после только сборки зависимостей, необходимых для делегата TF Lite.



Перейдите в каталог Arm NN build-tool, где находятся Dockerfile и связанные с ним скрипты.


```
cd armnn/build-tool
```


Запустите docker build, который загрузит и соберет Arm NN и его зависимости. Этот процесс изолирован от файловой системы хост-компьютера, в результате чего создается образ Docker.

Аргументы rfile передаются с помощью --build-arg, относительный путь к Dockerfile указывается с помощью --file, а текущий каталог — с помощью .

Укажите описательное название для изображения с помощью --tag в формате image_name:tag (пример приведен ниже). Обратная косая черта \ указывает Bash на необходимость продолжения команды в следующей строке.



В этом примере выбраны SETUP_ARGS и BUILD_ARGS для сборки всех компонентов Arm NN с ускоренными бэкендами NEON и OpenCL для архитектуры aarch64. Этот процесс должен занять менее часа на современном компьютере, но время может варьироваться в зависимости от выбранных аргументов и характеристик хост-компьютера.


```
docker build \
--build-arg SETUP_ARGS="--target-arch=aarch64 --all" \
--build-arg BUILD_ARGS="--target-arch=aarch64 --all --neon-backend --cl-backend" \
--tag armnn:aarch64 \
--file docker/Dockerfile .
```




Архив tarball со сборкой Arm NN находится в домашнем каталоге Docker (/home/arm-user/) и называется armnn__build.tar.gz. Если в --debug выше указан флаг сборки BUILD_ARGS, архив tarball будет называться armnn__build_debug.tar.gz.

Скрипт docker-copy-to-host.sh скопирует файл из образа Docker (в домашнем каталоге arm-user) на хост-компьютер.

Скрипт копирует архив tarball в новую папку на хосте в build-tool/docker_output. Он принимает два аргумента: image_name:tag и filename.

image_name — это относительный путь от домашнего каталога, созданного внутри образа Docker (/home/arm-user/).


```
./scripts/docker-copy-to-host.sh armnn:aarch64 armnn_aarch64_build.tar.gz
```


Этот архив теперь можно использовать для интеграции в приложение машинного обучения. Способ извлечения описан ниже.

Если --target-arch выбранное в аргументах выше устройство соответствует хост-компьютеру, сборку можно протестировать локально (в противном случае скопируйте архив на удаленное устройство).


```
cd docker_output

# Extract the tarball into a directory called _build
# If --debug is enabled, the extracted build directory will be called _build_debug
  
tar -xzf armnn_aarch64_build.tar.gz

cd aarch64_build

# Set LD_LIBRARY_PATH to the current aarch64_build directory (.)
export LD_LIBRARY_PATH=.; ./UnitTests

# If the Arm NN TF Lite Delegate is built, we can also run DelegateUnitTests
cd delegate

# Set LD_LIBRARY_PATH to the current delegate directory (.) and the aarch64_build directory (..)

export LD_LIBRARY_PATH=.:..; ./DelegateUnitTests
```




##### **Использование**

Собранный проект находится по пути "armnn/build-tool". В каталоге находятся модели (models), скрипты запуска, демо-видео (demo_video).

Т.к. динамический вход не поддерживается моделями, в каталоге "models" модели под разные разрешения:

1280*700

800*600

640*480

320*240

Входные кадры автоматически приводится к разрешению выбранной модели. От этого зависит качество и скорость работы модели.

  
**Запуск:**

  Для запуска EdgePoint2 необходимо, находясь в директории "build-tool" запустить скрипт demo_seq.py с обязательным указанием input:


```
python demo_seq.py demo_video/demo_video.mp4
```


Это запустит инференс модели с визуализацией на демонстрационном видео. Скрипт можно запускать с следующими параметрами:

input		|	Обязательный параметр. Ожидает путь к видеофайлу или значение "camera"
|--|--|
--camid	|		Id камеры. по умолчанию 0|
--top_k		|	Ограничитель количества выделенных признаков. По умолчанию 4096|
--match_threshold |	Пороговое значение для совпадения ключевых точек. По умолчанию 0.5|
--model	|		Путь к модели. По умолчанию "models/edgepoint2_E64_640_480.tflite"



**Пример запуска модели с камерой:**

```
python demo_seq.py camera \
--camid 0 \
--model_path models/edgepoint2_E64_320_240.tflite
```


##### **Краткое сравнение с оригинальной моделью:**

Среднее отклонение от оригинала в дескрипторах на выходе: 1%

Среднее отклонение в ключевых точках по координатам на выходе в среднем в пределах 6 пикселей

Разница в количестве обнаруженных ключевых точек в пределах 3% по сравнению с оригиналом


Для запуска модели CLIDD необходимо запустить скрипт:

```
python inference_clidd.py --model tflite_models/CLIDD/U128_640x480.tflite
```

Данный скрипт только запускает инференс модели CLIDD и выводит только средний FPS на отработанном видео.
Есть несколько конфигураций модели CLIDD. Все они находятся в "build-tool/models/CLIDD"
