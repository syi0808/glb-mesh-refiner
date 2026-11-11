CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra -pedantic

.PHONY: all test clean atlas-bake-test
all: glb_refine

glb_refine: src/refine.cpp
	$(CXX) $(CXXFLAGS) $< -o $@

test: glb_refine
	./glb_refine --self-test
	$(CXX) $(CXXFLAGS) tests/test_envelope.cpp -o tests/test_envelope
	./tests/test_envelope
	python3 tests/test_glb_pipeline.py
	$(MAKE) atlas-bake-test

clean:
	rm -f glb_refine glb_atlas_bake tests/test_envelope

atlas-bake-test: glb_atlas_bake
	python3 tests/test_atlas_bake.py

glb_atlas_bake: src/atlas_bake.cpp src/refine.cpp third_party/xatlas/xatlas.cpp third_party/xatlas/xatlas.h third_party/tinybvh/tiny_bvh.h third_party/tinybvh/tiny_bvh_base.h third_party/tinybvh/tiny_bvh_arm_double.h third_party/tinybvh/tiny_bvh_arm_float.h third_party/tinybvh/tiny_bvh_x86_double.h third_party/tinybvh/tiny_bvh_x86_float.h third_party/stb/stb_image.h third_party/stb/stb_image_write.h third_party/meshoptimizer_v1.3/src/meshoptimizer.h third_party/meshoptimizer_v1.3/src/simplifier.cpp third_party/meshoptimizer_v1.3/src/allocator.cpp
	$(CXX) $(CXXFLAGS) -Wno-sign-compare -pthread -DTINYBVH_NO_SIMD src/atlas_bake.cpp third_party/xatlas/xatlas.cpp third_party/meshoptimizer_v1.3/src/simplifier.cpp third_party/meshoptimizer_v1.3/src/allocator.cpp -o $@
