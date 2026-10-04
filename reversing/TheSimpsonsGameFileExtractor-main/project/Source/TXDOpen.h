#pragma once
#include <iostream>
#include <fstream>
#include <ostream>
#include <string>
#include <vector>
#include "Bytes.h"
#include <filesystem>
#include <cstdint>  // for uint32_t, uint8_t

#define DDS_UNCOMPRESSED      0x00000004  // DDPF_FOURCC
#define DDS_RGB         0x00000040  // DDPF_RGB
#define DDS_RGBA        0x00000041  // DDPF_RGB | DDPF_ALPHAPIXELS, althought u can just combine the first 2
#define DDPF_FOURCC		0x00000041
#define DDPF_YUV        0x00000200
#define DDS_LUMINANCE   0x00020000  // DDPF_LUMINANCE
#define DDS_LUMINANCEA  0x00020001  // DDPF_LUMINANCE | DDPF_ALPHAPIXELS
#define DDS_ALPHA       0x00000002  // DDPF_ALPHA
#define DDS_PAL8        0x00000020  // DDPF_PALETTEINDEXED8

#define DDS_HEADER_FLAGS_TEXTURE        0x00001007  // DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT, this is default, all textures NEED THIS ONE
#define DDS_HEADER_FLAGS_MIPMAP_COUNT   0x00020000  // DDSD_MIPMAPCOUNT
#define DDS_HEADER_FLAGS_DEPTH        0x00800000  // DDSD_DEPTH
#define DDS_HEADER_FLAGS_PITCH          0x00000008  // DDSD_PITCH
#define DDS_HEADER_FLAGS_LINEARSIZE     0x00080000  // DDSD_LINEARSIZE




#define DDS_SURFACE_FLAGS_TEXTURE 0x00001000 // DDSCAPS_TEXTURE
#define DDS_SURFACE_FLAGS_MIPMAP  0x00400008 // DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
#define DDS_SURFACE_FLAGS_CUBEMAP 0x00000008 // DDSCAPS_COMPLEX

#define DDS_CUBEMAP_POSITIVEX 0x00000600 // DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_POSITIVEX
#define DDS_CUBEMAP_NEGATIVEX 0x00000A00 // DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_NEGATIVEX
#define DDS_CUBEMAP_POSITIVEY 0x00001200 // DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_POSITIVEY
#define DDS_CUBEMAP_NEGATIVEY 0x00002200 // DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_NEGATIVEY
#define DDS_CUBEMAP_POSITIVEZ 0x00004200 // DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_POSITIVEZ
#define DDS_CUBEMAP_NEGATIVEZ 0x00008200 // DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_NEGATIVEZ


typedef uint32_t DWORD;
typedef uint8_t  BYTE;


#define MAKEFOURCC(ch0, ch1, ch2, ch3) \
    ((DWORD)(BYTE)(ch0) | ((DWORD)(BYTE)(ch1) << 8) | \
    ((DWORD)(BYTE)(ch2) << 16) | ((DWORD)(BYTE)(ch3) << 24))


struct DDSFlag {
	int FourCC;
	bool HasAlpha;
	int Filtering;
	bool HasSwizzle;
	bool HasMipMaps;

};

enum DDS_Data_Read {
	Uncompressed,
	DXT1,
	DXT2,
	DXT3,
	DXT4,
	DXT5,
	Default
};

class TXDOpen {

public:

	TXDOpen(){}

	TXDOpen(std::string _Name) {
		Name = _Name;
	}

	~TXDOpen() {};

	
	
	// this reads the file as binary and does process lines, needs to be called first
	void Init();

	// this loads the entire file into memory

	void ProcessLines(std::string Line, std::vector<unsigned char>& _Characters);

	// this will get us the geometry section of .rws, mind you not the ACTUAL geometry, thats later, but the chunk
	void ExtractData();

	//this is to add to our global output vector
	void ConvertToDDS(std::vector<uint8_t> InputData, std::string TextureName, int dwFlag, int FourCC, int FourCCFlags, DDS_Data_Read FourCCFormat,int Width, int Height, int FirstNumber,int LinerNumber, int MimMapCount,
		int Depth, bool IsGrey);

	void ConvertToDDSAlt(std::vector<uint8_t> InputData, std::string TextureName, int Width, int Height, int FirstNumber, int LinerNumber, int AlphaFlags, int MimMapCount,
		int Depth);


	//this is to get us to the actual geometry of the .rws file
	bool ProcessData(int _ObjectCount);

	void WriteToFile();


public:


	std::vector<int> OutputVector;

	std::string FilePath;

	// the whole purpose of this, is to make it impossible to have repeating files, no matter what
	int GlobalFileIndex = -1;

private:

	// this is a really cool methid, basically it breaks down bytes based on their size and converts the sections
	// i.e the hex bytes to uint8_t
	// this is really cool for specific integer sizes for files
	void WriteInt(std::ofstream& out, int value, int byteCount) {
		for (int i = 0; i < byteCount; ++i) {
			uint8_t byte = (value >> (i * 8)) & 0xFF;
			out.write(reinterpret_cast<char*>(&byte), 1);
		}
	}



	// Unswizzle from Morton layout to linear
	void UnswizzleAlt(const uint8_t* swizzled, uint8_t* linear, int width, int height, int bytesPerPixel) {
		int size = width * height;
		for (int i = 0; i < size; ++i) {
			int x, y;
			DecodeMorton2D(i, x, y);

			if (x >= width || y >= height)
				continue;

			int dstIndex = (y * width + x) * bytesPerPixel;
			int srcIndex = i * bytesPerPixel;

			memcpy(&linear[dstIndex], &swizzled[srcIndex], bytesPerPixel);
		}
	}


	// asigns our x and y via bitshitfting
	// this does it by virtue of odd even checks and asigning it to x and y
	// we do to 16 because we need it by rows, in hex edit and similar formatting its 16 for row, for our linaer
	void DecodeMorton2D(int index, int& x, int& y) {
		x = 0;
		y = 0;
		// thing is 16 for row
		for (int i = 0; i < 16; ++i) {
			// this determines odd or even, its a very low level way to do it, but we are on the 
			// lowest level near to assembly at this point, so im indifferent
			x |= ((index >> (2 * i + 0)) & 1) << i;
			y |= ((index >> (2 * i + 1)) & 1) << i;
		}
	}

	// basically tl;dr, morton layout or grid layout, basically lays your pixels out as maps/squares, however
	// other texture formats like .dds require linear, so we have to effectivelyconvert out pixels
	// AS WE ARE PARSING THEM THROUGH, to a linear format
	void Unswizzle(const uint8_t* swizzled, uint8_t* linear, int width, int height, int bytesPerPixel, DDS_Data_Read condition) {
		
		int size = 0.0f;
		for (int i = 0; i < size; ++i) {



			int x, y;
			DecodeMorton2D(i, x, y);


			if (x >= width || y >= height)
				continue;

		    if (condition == DDS_Data_Read::Uncompressed) {
				size = height * width;

				int dstIndex = (y * width + x) * bytesPerPixel;
				int srcIndex = i * bytesPerPixel;

				memcpy(&linear[dstIndex], &swizzled[srcIndex], bytesPerPixel);
			}

			if (condition == DDS_Data_Read::DXT1) {

			}

			if (condition == DDS_Data_Read::DXT3) {


				int dstIndex = (y * width + x);
				int srcIndex = i * bytesPerPixel;

				memcpy(&linear[dstIndex], &swizzled[srcIndex], bytesPerPixel);
			}

			if (condition == DDS_Data_Read::DXT5) {
				size = height * width;

				int dstIndex = (y * width + x) * bytesPerPixel;
				int srcIndex = i * bytesPerPixel;

				memcpy(&linear[dstIndex], &swizzled[srcIndex], bytesPerPixel);
			}
		}
	}


	void UnswizzleRGBA(const std::vector<uint8_t>& input, std::vector<uint8_t>& output, int width, int height, int bytes_per_pixel) {
		output.resize(input.size());

		for (int i = 0; i < width * height; ++i) {
			uint32_t x = DecodeMorton2X(i);
			uint32_t y = DecodeMorton2Y(i);

			if (x >= width || y >= height) continue;

			uint32_t dst_index = (y * width + x) * bytes_per_pixel;
			uint32_t src_index = i * bytes_per_pixel;

			std::memcpy(&output[dst_index], &input[src_index], bytes_per_pixel);
		}
	}

	void UnswizzleDXT(const std::vector<uint8_t>& input, std::vector<uint8_t>& output, int width, int height, int block_size) {
		int blocks_w = width / 4;
		int blocks_h = height / 4;

		output.resize(input.size());

		for (int i = 0; i < blocks_w * blocks_h; ++i) {
			uint32_t x = DecodeMorton2X(i);
			uint32_t y = DecodeMorton2Y(i);

			if (x >= blocks_w || y >= blocks_h) continue;

			uint32_t dst_index = (y * blocks_w + x) * block_size;
			uint32_t src_index = i * block_size;

			std::memcpy(&output[dst_index], &input[src_index], block_size);
		}
	}


	inline uint32_t Compact1By1(uint32_t x) {
		x &= 0x55555555;
		x = (x ^ (x >> 1)) & 0x33333333;
		x = (x ^ (x >> 2)) & 0x0f0f0f0f;
		x = (x ^ (x >> 4)) & 0x00ff00ff;
		x = (x ^ (x >> 8)) & 0x0000ffff;
		return x;
	}

	inline uint32_t DecodeMorton2X(uint32_t index) {
		return Compact1By1(index >> 0);
	}

	inline uint32_t DecodeMorton2Y(uint32_t index) {
		return Compact1By1(index >> 1);
	}


	void PadGrayscaleToTopLeft_RGBA(
		const uint8_t* grayscale, // original grayscale buffer (1 byte per pixel)
		uint8_t* rgba,            // destination RGBA buffer (pre-allocated)
		int srcWidth, int srcHeight,
		int dstWidth, int dstHeight)
	{
		for (int y = 0; y < dstHeight; ++y)
		{
			for (int x = 0; x < dstWidth; ++x)
			{
				
				int dstIndex = (y * dstWidth + x) * 4;

				if (x < srcWidth && y < srcHeight)
				{
					int srcIndex = y * srcWidth + x;
					uint8_t g = grayscale[srcIndex];

					rgba[dstIndex + 0] = grayscale[srcIndex + 0];
					rgba[dstIndex + 1] = grayscale[srcIndex + 1];
					rgba[dstIndex + 2] = grayscale[srcIndex + 2];
					rgba[dstIndex + 3] = grayscale[srcIndex + 3];
				}
				else
				{
					rgba[dstIndex + 0] = 102;
					rgba[dstIndex + 1] = 67;
					rgba[dstIndex + 2] = 70;
					rgba[dstIndex + 3] = 255;
				}
			}
		}
	}


private:

	int GlobalFileOffset;

	std::fstream FileObject;

	std::string Name;

	std::vector<unsigned char> Characters;
};