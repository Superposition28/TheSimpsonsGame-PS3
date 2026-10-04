#include "TXDOpen.h"

void TXDOpen::Init()
{
	if (Characters.size() > 0) {
		return;
	}

	std::ifstream EntireFile(Name.c_str(), std::ios::binary | std::ios::ate);
	if (!EntireFile.is_open()) {
		std::cerr << "Cannot open file: " << Name.c_str() << "\n";
		return;
	}


	std::streamsize fileSize = EntireFile.tellg();
	EntireFile.seekg(0, std::ios::beg);

	if (fileSize <= 0) {
		std::cerr << "File size invalid or empty file: " << Name.c_str() << "\n";
		return;
	}

	std::vector<char> buffer(fileSize);

	if (!EntireFile.read(buffer.data(), fileSize)) {
		std::cerr << "Failed to read file content.\n";
		return;
	}

	EntireFile.close();

	for (char ch : buffer) {
		ProcessLines(std::string(1, ch), Characters);
	}

	std::cout << "Completed the Init " << buffer.size() << " Is the Buffer Size\n";
}

void TXDOpen::ProcessLines(std::string Line, std::vector<unsigned char>& _Characters)
{
	int Length = Line.size();

	for (int i = 0; i < Length; i++) {
		_Characters.push_back(Line[i]);

	}
}

void TXDOpen::ExtractData()
{

	int HeaderSize = 144;

	int Offset = 0;

	Chunk Clump = Chunk(Characters.begin(), Offset);

	int FileSigComparison = 22;

	if (!(Clump.type == FileSigComparison)) {
		std::cerr << "Error this is not the correct file" << std::endl;
		return;
	}

	// first struct moves offset
	Chunk StartStruct = Chunk(Characters.begin(), Offset);


	// offset is moved by this, DO NOT MOVE IT AGAIN U SWINE
	std::vector<uint8_t> HeaderInfo_1 = StartStruct.Process(Characters, Offset);

	int AmountOfTextures = Char_Byte(HeaderInfo_1.begin(), HeaderInfo_1.begin() + 2).CastToint16_LE().variable;

	int Unknown = Char_Byte(HeaderInfo_1.begin() + 2, HeaderInfo_1.begin() + 4).CastToint16_LE().variable;

	

	for (int i = 0; i < AmountOfTextures; i++) {

		DDS_Data_Read FourCC = DDS_Data_Read::Default;
		int FourCCFlags = 0;
		int FourCCHex = 0;
		int LocalOffset = 0;

		bool IsGreyScaled = false;

		Chunk Field = Chunk(Characters.begin(), Offset);

		std::vector<uint8_t> TextureData = Char_Byte(Characters.begin() + Offset, Characters.begin() + Offset + Field.size).Char_Bytes;

		Offset += TextureData.size();

		Chunk TextureChunk = Chunk(TextureData.begin(), LocalOffset);

		int Flags = Char_Byte(TextureData.begin(), LocalOffset, 4).CastToint32_LE().variable;

		int FilterFlags = Char_Byte(TextureData.begin(), LocalOffset, 4).CastToint32_LE().variable;

		std::string TextureName(TextureData.begin() + LocalOffset, TextureData.begin() + LocalOffset + 32);

		std::string AlphaName(TextureData.begin() + LocalOffset, TextureData.begin() + LocalOffset + 32);

		LocalOffset += 64;

		int directid = Char_Byte(TextureData.begin(), LocalOffset, 4).CastToint32_BE().variable;

		// this is actually the compression type
		int AlphaFlags = Char_Byte(TextureData.begin(), LocalOffset, 4).CastToint32_BE().variable;

		int bpp = 0;

		int channels = 0;

		std::vector<uint8_t> GreyVector(TextureData.size() * 4);




		int Width = Char_Byte(TextureData.begin(), LocalOffset, 2).CastToint16_BE().variable;

		int Height = Char_Byte(TextureData.begin(), LocalOffset, 2).CastToint16_BE().variable;

		if (AlphaFlags == 405275014) {
			FourCC = Uncompressed;
			FourCCFlags = 0x00000041;
			FourCCHex = 0x00000000;
			bpp = 8;
			channels = 4;
		}

		else if (AlphaFlags == 671088898) {
			FourCC = Uncompressed;
			FourCCFlags = 0x00000040;
			FourCCHex = 0x00000000;
			bpp = 8;
			channels = 1;
			IsGreyScaled = true;

			//PadGrayscaleToTopLeft_RGBA(TextureData.data(), GreyVector.data(), Width, Height, Width, Height );


		}

		else if (AlphaFlags == 438305106) {
			FourCC = DXT1;
			FourCCFlags = 0x00000004;
			FourCCHex = 0x31545844;
			bpp = 4;
			channels = 3;


		}

		else if (AlphaFlags == 438305109) { 
			FourCC = DXT2;
			FourCCFlags = 0x00000004;
			FourCCHex = 0x32545844;
			bpp = 8;
			channels = 4;
		}

		

		else if (AlphaFlags == 438305107) {
			FourCC = DXT3;
			FourCCFlags = 0x00000004;
			FourCCHex = 0x33545844;
			bpp = 8;
			channels = 4;
		}

		else if (AlphaFlags == 438305110) { 
			FourCC = DXT4;
			FourCCFlags = 0x00000004;
			FourCCHex = 0x34545844;
			bpp = 8;
			channels = 4;
		}

		else if (AlphaFlags == 438305108) {
			FourCC = DXT5;
			FourCCFlags = 0x00000004;
			FourCCHex = 0x35545844;
			bpp = 8;
			channels = 4;
		}

		else {
			int gh = 0;
		}



		int Depth = TextureData[LocalOffset++];

		int mipmap_count = TextureData[LocalOffset++];

		int text_coord_type = TextureData[LocalOffset++];

		int MoreFlags = TextureData[LocalOffset++];

		int Palette = TextureData[Depth == 8 ? 256 * 4 : 0];

		// this is basically the size of the texture, the rest are mip maps, can be used for relative offset
		int SizeOfInitialMip = Char_Byte(TextureData.begin(), LocalOffset, 4).CastToUint32_LE().variable;

		TextureData.erase(TextureData.begin(), TextureData.begin() + LocalOffset);

		// nothing for now
		int dwFlag = 0;

		// because we are converting from texture, its always true, so we do 0x1, 0x2, 0x4
		dwFlag |= 0x7;

		// if the fourCC is compressed we need to add pitch flag
		if (FourCC != DXT1 && FourCC != DXT3 && FourCC != DXT5) {
			dwFlag |= 0x8;
		}

		else {
			dwFlag |= 0x80000;
		}

		// this is standard
		dwFlag |= 0x1000;
		
		// if we have mipmaps
		if (mipmap_count > 0) {
			dwFlag |= 0x20000;
		}


		int total_bpp = bpp * channels;
		int Pitch = ((Width * total_bpp + 7) / 8 + 3) & ~3;


		if (IsGreyScaled) {
			return;
		}

		// now its time to convert data

		/*if (!IsGreyScaled) {
			ConvertToDDS(TextureData, TextureName, dwFlag, FourCCHex, FourCCFlags, FourCC, Width, Height, SizeOfInitialMip, Pitch, mipmap_count, Depth, IsGreyScaled);
		}
		
		else {
			ConvertToDDS(GreyVector, TextureName, dwFlag, FourCCHex, FourCCFlags, FourCC, Width, Height, SizeOfInitialMip, Pitch, mipmap_count, Depth, IsGreyScaled);
		}*/
		ConvertToDDS(TextureData, TextureName, dwFlag, FourCCHex, FourCCFlags, FourCC, Width, Height, SizeOfInitialMip, Pitch, mipmap_count, Depth, IsGreyScaled);
	}





}

void TXDOpen::ConvertToDDS(std::vector<uint8_t> InputData, std::string TextureName, int dwFlag, int FourCC, int FourCCFlags, DDS_Data_Read FourCCFormat ,int Width, int Height, int FirstOffset, int LinearNumber, int MinMapCount,int Depth, bool IsGrey)
{

	

	std::string name = "";

	GlobalFileIndex++;

	TextureName = TextureName.substr(0, TextureName.find('\0')); 
	TextureName.shrink_to_fit();

	name.append(std::string(TextureName));
	name.shrink_to_fit();
	name.append(std::to_string(GlobalFileIndex));
	name.append(".dds");



	std::filesystem::path OutputPath = std::filesystem::path(FilePath) / name;

	std::ofstream Output(OutputPath, std::ios::binary);



	// DDs Signature, dont change
	WriteInt(Output, 0x20534444, 4);

	// size of header, always the same so dont change
	WriteInt(Output, 0x0000007C, 4);

	// i think these are flags, i dont know
	WriteInt(Output, dwFlag, 4);

	// good, have to be big number tho, like none of that ratio shit, 1024, 512 etc those are cool
	WriteInt(Output, Height, 4);

	WriteInt(Output, Width, 4);

	// this number can be really big or small, like 4096


	// linear number refers to the size of the ENTIRE first texture image in bytes
	// this number CAN be pitch instead, in that case its the number per row of pixels
	// if this number is fucking massive, its linear size, if its way smaller its pitch, it variable and cringe
	WriteInt(Output, LinearNumber, 4);


	// depth of volume texture, bruh this is ps3, there aint no fucking volume in textures HAHAHHAHAHA
	WriteInt(Output, 0x00000001, 4);

	WriteInt(Output, MinMapCount, 4);

	// preallocate 11 bytes

	for (int i = 0; i < 11; i++) {
		WriteInt(Output, 0x00000000, 4);
	}


	// other size
	WriteInt(Output, Depth, 4);

	// flags
	WriteInt(Output, FourCCFlags, 4);

	// the fourCC or special characters that denote the directX thingy ( its a magic number basically)
	WriteInt(Output, FourCC, 4);

	// RGBBitCount
	WriteInt(Output, Depth, 4);


	// RBitMask
	WriteInt(Output, 0x00FF0000, 4);

	// GBitMask
	WriteInt(Output, 0x0000FF00, 4);

	// BBitMask
	WriteInt(Output, 0x000000FF, 4);

	// ABitMask

	if (IsGrey) {
		WriteInt(Output, 0x00000000, 4);
	}

	else {
		WriteInt(Output, 0xFF000000, 4);
	}


	if (MinMapCount > 0) {
		// Caps 1
		WriteInt(Output, 0x00401008, 4);
	}

	else {
		WriteInt(Output, 0x00001000, 4);
	}

	// these are all useless

	// Caps 2
	WriteInt(Output, 0x00000000, 4);

	// Caps 3
	WriteInt(Output, 0x00000000, 4);

	// Caps 4
	WriteInt(Output, 0x00000000, 4);

	// Reserved 
	WriteInt(Output, 0x00000000, 4);


 


	// this isnt needed, BUT, if we find a format where we need to swap from rgba to bgra, KEEP THIS
	//for (size_t i = 0; i < InputData.size(); i += 4) {
	//	std::swap(InputData[i], InputData[i + 2]); // Swap R and B
	//}


	// After reorienting, you can now write the data to the .dds file
	if (!Output.is_open()) {
		return;
	}







	int MipOffset = 0;

	int NewWidth;
	int NewHeight;
	int channels;

	int BlockSize = 16;

	int size; // = NewWidth * NewHeight * BlockSize;

	if (FourCCFormat == DXT1) {
		BlockSize = 8;

		NewWidth = std::max(1, (Width + 3) / 4);
		NewHeight = std::max(1, (Height + 3) / 4);

		channels = 3;

		//size = NewWidth * NewHeight * BlockSize;
	}

	else if (FourCCFormat == DXT2 || FourCCFormat == DXT3 || FourCCFormat == DXT4 || FourCCFormat == DXT5) {
		BlockSize = 16;

		NewWidth = std::max(1, (Width + 3) / 4);
		NewHeight = std::max(1, (Height + 3) / 4);

		channels = 4;

		//size = NewWidth * NewHeight * BlockSize;


	}

	else if (IsGrey) {
		NewWidth = Width;
		NewHeight = Height;

		channels = 1;
	}

	else {
		NewWidth = Width;
		NewHeight = Height;

		channels = 4;

		//size = NewWidth * NewHeight * channels;
	}

	

	

	

	std::vector<int> MipMapOffsets; 
	MipMapOffsets.push_back(0);

	int PriorSize = 0;

	// ok these work
	for (int i = 0; i < MinMapCount; i++) {
		
		if (MinMapCount == 1) {
			Output.write(reinterpret_cast<const char*>(InputData.data()), InputData.size());
			continue;
		}

		
			
		
		if (FourCCFormat == DXT1 || FourCCFormat == DXT2 || 
			FourCCFormat == DXT3 || FourCCFormat == DXT4 || 
			FourCCFormat == DXT5) {
			size = NewWidth * NewHeight * BlockSize;
		}

		else {
			size = NewWidth * NewHeight * channels;
		}
		

		Char_Byte Text = Char_Byte(InputData.begin()  + PriorSize, InputData.begin() + PriorSize + size);

		NewWidth *= 0.5;
		NewHeight *= 0.5;

		PriorSize += size;
		PriorSize += 4;
	

		MipMapOffsets.push_back(PriorSize);

		

	}

	NewWidth = Width;
	NewHeight = Height;


	for (int Mip = 0; Mip < MipMapOffsets.size() - 1; ++Mip) {
		



		int MipStartOffset = MipMapOffsets[Mip];
		int MipEndOffset = MipMapOffsets[Mip + 1];

		MipEndOffset -= 4;


		std::vector<uint8_t> PollFrom = Char_Byte(InputData.begin() + MipStartOffset, InputData.begin()  + MipEndOffset).Char_Bytes;


		int Displacement = MipEndOffset - MipStartOffset;



		std::vector<uint8_t> ddsPixels;

		if (FourCCFormat == DDS_Data_Read::DXT1 || 
			FourCCFormat == DDS_Data_Read::DXT2 ||
			FourCCFormat == DDS_Data_Read::DXT3 ||
			FourCCFormat == DDS_Data_Read::DXT4 ||
			FourCCFormat == DDS_Data_Read::DXT5 || 
			IsGrey) {


			//UnswizzleDXT(PollFrom, ddsPixels, NewWidth, NewHeight, BlockSize);
			//Output.write(reinterpret_cast<const char*>(ddsPixels.data()), ddsPixels.size());

			Output.write(reinterpret_cast<const char*>(PollFrom.data()), PollFrom.size());
		}

		else {
			UnswizzleRGBA(PollFrom, ddsPixels, NewWidth, NewHeight, channels);
			Output.write(reinterpret_cast<const char*>(ddsPixels.data()), ddsPixels.size());
		}

		

		
		 

		NewWidth = std::max(1, NewWidth / 2);
		NewHeight = std::max(1, NewHeight / 2);

	}
	

	Output.close();

}


















void TXDOpen::ConvertToDDSAlt(std::vector<uint8_t> InputData, std::string TextureName, int Width, int Height, int FirstNumber, int LinerNumber, int AlphaFlags, int MimMapCount, int Depth)
{
	int HeaderSize = 128;

	std::ofstream Output("Out.dds", std::ios::binary);

	// DDs Signature
	WriteInt(Output, 0x20534444, 4);

	// size of header
	WriteInt(Output, 0x0000007C, 4);


	WriteInt(Output, 0x0002100F, 4);

	WriteInt(Output, Width, 4);

	WriteInt(Output, Height, 4);

	WriteInt(Output, LinerNumber, 4);

	WriteInt(Output, 0x00000001, 4);

	WriteInt(Output, MimMapCount, 4);

	// preallocate 11 bytes

	for (int i = 0; i < 11; i++) {
		WriteInt(Output, 0x00000000, 4);
	}


	// other size
	WriteInt(Output, Depth, 4);

	// flags
	WriteInt(Output, 0x00000041, 4);

	// the fourCC or special characters that denote the directX thingy ( its a magic number basically)
	WriteInt(Output, 0x00000000, 4);

	// RGBBitCount
	WriteInt(Output, 0x00000020, 4);


	// RBitMask
	WriteInt(Output, 0x00FF0000, 4);

	// GBitMask
	WriteInt(Output, 0x0000FF00, 4);

	// BBitMask
	WriteInt(Output, 0x000000FF, 4);

	// ABitMask
	WriteInt(Output, 0xFF000000, 4);

	// Caps 1
	WriteInt(Output, 0x00401008, 4);

	// Caps 2
	WriteInt(Output, 0x00000000, 4);

	// Caps 3
	WriteInt(Output, 0x00000000, 4);

	// Caps 4
	WriteInt(Output, 0x00000000, 4);

	// Reserved 
	WriteInt(Output, 0x00000000, 4);





	// this isnt needed, BUT, if we find a format where we need to swap from rgba to bgra, KEEP THIS
	//for (size_t i = 0; i < InputData.size(); i += 4) {
	//	std::swap(InputData[i], InputData[i + 2]); // Swap R and B
	//}


	// After reorienting, you can now write the data to the .dds file
	if (!Output.is_open()) {
		return;
	}





	int counter = 1;

	int MipOffset = 0;

	int NewWidth = Width / counter;
	int NewHeight = Height / counter;
	int channels = 4;

	int size = (NewWidth * NewHeight) * channels;

	std::vector<int> MipMapOffsets;
	MipMapOffsets.push_back(0);


	// ok these work
	for (int i = 0; i < MimMapCount; i++) {

		if (MimMapCount == 1) {
			Output.write(reinterpret_cast<const char*>(InputData.data()), InputData.size());
			continue;
		}

		uint32_t Next = Char_Byte(InputData.begin() + size + MipOffset, InputData.begin() + size + MipOffset + 4).CastToUint32_LE().variable;

		MipOffset += 4;

		MipMapOffsets.push_back(MipOffset + size);

		MipOffset += Next;

	}


	for (int Mip = 0; Mip < MipMapOffsets.size() - 1; Mip++) {


		int Newsize = NewWidth * NewHeight * channels;

		int NewMipMapOffset = MipMapOffsets[Mip];

		std::vector<uint8_t> PollFrom = Char_Byte(InputData.begin() + NewMipMapOffset, InputData.begin() + NewMipMapOffset + Newsize).Char_Bytes;



		uint8_t* ddsPixels = new uint8_t[NewWidth * NewHeight * channels];

		//for (int j = 0; j < NewHeight; ++j) {
		//	for (int i = 0; i < NewWidth; ++i) {
		//		int srcIndex = (j * NewWidth + i) * channels;
		//		//int dstIndex = (j * NewWidth + i) * channels;
		//		int dstIndex = srcIndex;

		//		ddsPixels[dstIndex + 0] = PollFrom[srcIndex + 0];
		//		ddsPixels[dstIndex + 1] = PollFrom[srcIndex + 1];
		//		ddsPixels[dstIndex + 2] = PollFrom[srcIndex + 2];
		//		ddsPixels[dstIndex + 3] = PollFrom[srcIndex + 3]; // PollFrom[srcIndex + 3];
		//	}
		//}

		Unswizzle(PollFrom.data(), ddsPixels, NewWidth, NewHeight, channels, DDS_Data_Read::Default);

		Output.write(reinterpret_cast<const char*>(ddsPixels), (NewWidth * NewHeight * channels));

		delete[] ddsPixels;

		NewWidth = std::max(1, NewWidth / 2);
		NewHeight = std::max(1, NewHeight / 2);

	}



	//for (int i = 0; i < InputData.size(); i++) {
	//	WriteInt(Output, InputData[i], 1);
	//}


	//Output.write(reinterpret_cast<const char*>(InputData.data()), InputData.size());
	Output.close();
}


bool TXDOpen::ProcessData(int _ObjectCount)
{
	return false;
}

void TXDOpen::WriteToFile()
{

}
