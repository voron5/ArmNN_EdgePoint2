#
# Copyright © 2020 Arm Ltd and Contributors. All rights reserved.
# SPDX-License-Identifier: MIT
#

get_filename_component(ARMNN_DELEGATE_CMAKE_DIR "${CMAKE_CURRENT_LIST_FILE}" DIRECTORY)
set(ARMNN_DELEGATE_CONFIG_FILE ${CMAKE_CURRENT_LIST_FILE})
MESSAGE(STATUS "Found ArmnnDelegate: ${ARMNN_DELEGATE_CONFIG_FILE}")

include(CMakeFindDependencyMacro)

list(APPEND CMAKE_MODULE_PATH ${ARMNN_DELEGATE_CMAKE_DIR})


####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was ArmnnDelegateConfig.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../" ABSOLUTE)

macro(set_and_check _var _file)
  set(${_var} "${_file}")
  if(NOT EXISTS "${_file}")
    message(FATAL_ERROR "File or directory ${_file} referenced by variable ${_var} does not exist !")
  endif()
endmacro()

macro(check_required_components _NAME)
  foreach(comp ${${_NAME}_FIND_COMPONENTS})
    if(NOT ${_NAME}_${comp}_FOUND)
      if(${_NAME}_FIND_REQUIRED_${comp})
        set(${_NAME}_FOUND FALSE)
      endif()
    endif()
  endforeach()
endmacro()

####################################################################################
set_and_check(Armnn_DIR "")
find_dependency(Armnn REQUIRED CONFIG HINTS ${Armnn_DIR})

if(NOT TARGET ArmnnDelegate::ArmnnDelegate)
    MESSAGE(STATUS "ArmnnDelegate Import: ${ARMNN_DELEGATE_CMAKE_DIR}/ArmnnDelegateTargets.cmake")
    include("${ARMNN_DELEGATE_CMAKE_DIR}/ArmnnDelegateTargets.cmake")
endif()

set(ARMNN_DELEGATE_LIBRARIES ArmnnDelegate::ArmnnDelegate)
