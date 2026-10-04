#include "Str_Load_Full.h"



void Str_Load_Full::init(const char* file)
{
	Filename = (char*)file;

	std::ifstream EntireFile(Filename, std::ios::binary | std::ios::ate);
	if (!EntireFile.is_open()) {
		std::cerr << "Cannot open file: " << Filename << "\n";
		return;
	}


	std::streamsize fileSize = EntireFile.tellg();
	EntireFile.seekg(0, std::ios::beg);

	if (fileSize <= 0) {
		std::cerr << "File size invalid or empty file: " << Filename << "\n";
		return;
	}

	std::vector<char> buffer(fileSize);

	if (!EntireFile.read(buffer.data(), fileSize)) {
		std::cerr << "Failed to read file content.\n";
		return;
	}

	EntireFile.close();

	for (char ch : buffer) {
		SortGarbeld(std::string(1, ch));  
	}

    std::cout << "Completed the Init " << buffer.size() << " Is the Buffer Size\n";

}



void Str_Load_Full::WriteSectionToFile(std::ofstream& OutFile, std::vector<uint8_t> Data, int index)
{
	if (!OutFile.is_open()) {
		return;
	}

	std::string Name = std::to_string(index);

	if (!Data.empty()) {
		OutFile.write((const char*)(Data.data()), Data.size());
	}
}

void Str_Load_Full::WriteSectionToFile(std::ofstream& OutFile, std::vector<uint8_t> Data)
{
	if (!OutFile.is_open()) {
		return;
	}

	if (!Data.empty()) {
		OutFile.write((const char*)(Data.data()), Data.size());
	}
}

void Str_Load_Full::UnCompressSection(std::vector<char> InData,std::vector<uint8_t> &OutData, size_t InSize, size_t OutSize)
{
	Scanner in, out;

	uint16_t sig;
	uint8_t Byte_Zero, Byte_One, Byte_Two, Byte_Three;
	uint32_t CompSize, DecompSize;
	uint32_t proc_len, ref_dis, ref_len;


	//std::vector<uint8_t> InDataReal;

	/*for (int i = 0; i < InData.size(); i++) {
		InDataReal.push_back((uint8_t) InData[i]);
	}*/


	Init(&in, reinterpret_cast<std::vector<uint8_t>*>(&InData), InSize);
	Init(&out, &OutData, OutSize);


	sig = read_u16(&in);

	CompSize = (sig & 0x0100) ? read_u24(&in) : 0;

	DecompSize = read_u24(&in);


	while (!overflowed(&in) && !overflowed(&out))
	{
		Byte_Zero = read_u8(&in);

		// 0x80 is for 128, conviniently the size of a signed char  

		if (!(Byte_Zero & 0x80)) {

	

			Byte_One = read_u8(&in);

			proc_len = Byte_Zero & 0x03;
			append(&out, &in, proc_len);

			ref_dis = ((Byte_Zero & 0x60) << 3) + Byte_One + 1;
			ref_len = ((Byte_Zero >> 2) & 0x07) + 3;

			self_copy(&out, ref_dis, ref_len);
		}

		// 0x40 is for 64, half of a char

		else if (!(Byte_Zero & 0x40)) {




			Byte_One = read_u8(&in);
			Byte_Two = read_u8(&in);

			proc_len = Byte_One >> 6;
			append(&out, &in, proc_len);

			ref_dis = ((Byte_One & 0x3f) << 8) + Byte_Two + 1;
			ref_len = (Byte_Zero & 0x3f) + 4;
			self_copy(&out, ref_dis, ref_len);
		}

		// 0x20 is for 32, quater of a char

		else if (!(Byte_Zero & 0x20)) {


			Byte_One = read_u8(&in);
			Byte_Two = read_u8(&in);
			Byte_Three = read_u8(&in);

			proc_len = Byte_Zero & 0x03;
			append(&out, &in, proc_len);

			ref_dis = ((Byte_Zero & 0x10) << 12) + (Byte_One << 8) + Byte_Two + 1;
			ref_len = ((Byte_Zero & 0x0c) << 6) + Byte_Three + 5;
			self_copy(&out, ref_dis, ref_len);

		}




		else {



			proc_len = (Byte_Zero & 0x1f) * 4 + 4;

			if (proc_len <= 0x70) {
				append(&out, &in, proc_len);
			}
			 
			else {
				proc_len = Byte_Zero & 0x3;
				append(&out, &in, proc_len);
				break;  
			}
		}
	}
}

void Str_Load_Full::UnCompress()
{
	int index = 0;
	


	if (!std::filesystem::exists(USFP.c_str())) {
		if (std::filesystem::create_directory(USFP.c_str())) {
			std::cout << " Created the folder " << " " << USFP.c_str() << std::endl;
		}

	}
	

	for (int i = 0; i < SectionList.size(); i++) {
		index++;

		std::string name = std::to_string(index);



		std::filesystem::path FilePath = std::filesystem::path(USFP) / name;
	
		std::ofstream TempOutput(FilePath, std::ios::binary);

		std::vector<char> InData = SectionList[i].SectionReal;
		std::vector<uint8_t> OutData(SectionList[i].UnCompressedSize.variable);

		size_t InSize = (size_t)InData.size();
		size_t OutSize = (size_t)OutData.size();




		if (SectionList[i].CompressedSize.variable >= SectionList[i].UnCompressedSize.variable) {
			WriteSectionToFile(TempOutput, std::vector<uint8_t>(InData.begin(), InData.end()), index);
		}

		else {
			UnCompressSection(InData, OutData, InSize, OutSize);
			WriteSectionToFile(TempOutput, OutData, index);
		}


		

		// write section to file was also here, redo if breaks
		
		

		TempOutput.close();

		

		printf("\n");
	}

	SectionList.clear();
	SectionList.shrink_to_fit();
}


void Str_Load_Full::SortGarbeld(std::string CurrentLine) {

	int Size = CurrentLine.size();

	for (int j = 0; j < Size; j++) {

		AllList.push_back(CurrentLine[j]);

	
	
	}	
}

void Str_Load_Full::SortGarbeld(std::string CurrentLine, std::vector<uint8_t>& Output) {
	int Size = CurrentLine.size();

	for (int j = 0; j < Size; j++) {

		Output.push_back(CurrentLine[j]);



	}
}

		
void Str_Load_Full::CheckHeaderForCompression()
{

	int Offset = 16;

	const int InitialOffSet = Char_Byte(AllList.begin(), Offset, 4).CastToint32_BE().variable; //where the section part starts

	const int HeaderSize = 24; //how big each section IN THE HEADER is (obviously not size of actual headers)
	
	Sections = AllList[8]; // the amount of sections i.e its just a number

	std::vector<unsigned char>::iterator StartIndexIterator = AllList.begin() + InitialOffSet;


	// this compiles a list of all of the header section file, 24 bytes each respective
	for (int i = 0; i < Sections.variable; i++) {

		std::vector<unsigned char>::iterator Start = StartIndexIterator + (i * HeaderSize);
		std::vector<unsigned char>::iterator End = StartIndexIterator + (i * HeaderSize) + HeaderSize;


		Section SectionSlice = Section{};

		SectionSlice.SectionHeader.insert(SectionSlice.SectionHeader.begin(), Start, End);
		SectionSlice.SizeHeader = 24;

		SectionList.push_back(SectionSlice);
	}

	int Capacity = AllList.capacity();
	int Size = AllList.size();

	for (int i = 0; i < SectionList.size(); i++) 
	{
		
	
		

		Char_Byte CompressedSize = Char_Byte(SectionList[i].SectionHeader.begin() + 16, SectionList[i].SectionHeader.begin() + 20);

		Char_Byte UnCompressedSize = Char_Byte(SectionList[i].SectionHeader.begin() + 8, SectionList[i].SectionHeader.begin() + 12);



		SectionList[i].CompressedSize = CompressedSize.CastToUint32_BE();
		SectionList[i].UnCompressedSize = UnCompressedSize.CastToUint32_BE();
		

	}



	// hard coded locations where the files start, the end via the offset plus the size of the file which is compressed, meaning get the offset, and add its compressed size, to get to where you need to be, assuming of course they are compressed.

	int Pushed = 2048;

	for (int i = 0; i < SectionList.size(); i++) {
		
		int Start = Pushed;
		
	    Pushed += SectionList[i].CompressedSize.variable;

		int End = Pushed;

	    SectionList[i].SectionReal.insert(SectionList[i].SectionReal.begin(), AllList.begin() + Start, AllList.begin() + End);
		
	}

	AllList.clear();
	AllList.shrink_to_fit();
}



bool Str_Load_Full::IsStrFile(std::ifstream& file)
{

	std::string Line;
	std::string SToc = "SToc";

	std::getline(file, Line);

	if (Line.compare(SToc) == 1) {
		file.close();
		return true;
	}

	else {
		file.close();
		return false;
	}

	return false;
}

void Str_Load_Full::ExtractSection(const char* FileName)
{
	// load file from file name, this will be one of our sections
	std::ifstream File(FileName, std::ios::binary | std::ios::ate);

	//loads file into Output
	std::vector<uint8_t> Output;

	if (!File.is_open()) {
		std::cerr << "Cannot open file: " << Filename << "\n";
		return;
	}


	std::streamsize fileSize = File.tellg();
	File.seekg(0, std::ios::beg);

	if (fileSize <= 0) {
		std::cerr << "File size invalid or empty file: " << Filename << "\n";
		return;
	}

	std::vector<uint8_t> buffer(fileSize);

	if (!File.read(reinterpret_cast<char*>(buffer.data()), fileSize)) {
		std::cerr << "Failed to read file content.\n";
		return;
	}

	File.close();


	// line by line adds to output
	for (uint8_t ch : buffer) {

		SortGarbeld(std::string(1, ch), Output);
	}


	std::cout << " Section Loaded In" << buffer.size() << " Is the Buffer Size\n";


	// basically if this is true by virtue of there not being another file, we stop
	bool OverFlown = false;

	// this is to be added on, a running offset
	unsigned int Offset = 0;


	// name of the file we are gonna output, this will also change
	std::string Name;

	// standard termination clause is 0

	uint8_t TerminationClause8 = 0;

	// basically, most structures, offsets etc are terminated with 0x00BF which translates to 191 unsigned 16
	uint16_t TerminationClause16 = 191;

	// another termination clause for blank strings is 0x00BFBFBF

	uint32_t TerminationClause32 = 12566463;

	// if this is ever equal to our name, we have hit a texture, so we need to rename
	int TextureValue = 12566463;



	while (!OverFlown) {

		if (Offset >= Output.size()) {
			OverFlown = true;
			break;
		}



		int StartOfSubFile = Offset;

		// this has to be 16 07 or its not uncompressed
		Char_Byte SigPre = Char_Byte{ Output.begin() + Offset, Output.begin() + Offset + 2 };

		// converts to actual number
		uint16_t SigPost = SigPre.CastToUint16_LE().variable;

		if (SigPost != 1814) {
			OverFlown = true;
			break;
		}

		Offset += 4;


		//this is how big the file is, its also technically a 24 bit number, but 32 works and 24 sucks anyway
		Char_Byte MemoryOffset = Char_Byte{ Output.begin() + Offset, Output.begin() + Offset + 4 };

		int MemOut = MemoryOffset.CastToint32_LE().variable;

		Offset += 8;


		// this is the 17th byte to 20th byte big endian number that gives our first offset to D18E
		Char_Byte OffsetOne = Char_Byte{ Output.begin() + Offset, Output.begin() + Offset + 4 };

		uint32_t OffsetOneData = OffsetOne.CastToint32_BE().variable;

		int AddSizeToMe = Offset;

		Offset += 4;


		int AddOffsetOneDataToMe = Offset;

		// this is the number that denotes where the file ACTUALLY starts i.e each file has a header file, this is after that.



		Char_Byte StartOfFile = Char_Byte{ Output.begin() + Offset, Output.begin() + Offset + 4 };

		// this is the size of the file name
		uint32_t Start = StartOfFile.CastToint32_BE().variable;

		Offset += 4;


		Char_Byte FileName = Char_Byte{ Output.begin() + Offset, Output.begin() + Offset + Start };


		std::string TempFileName(FileName.Char_Bytes.begin(), FileName.Char_Bytes.end());

		TempFileName = StringIndexes(TempFileName, ObjectIndex);


		Offset += FileName.Char_Bytes.size();



		// 16 is how big the proceeding structure and 1 for the Termination clause 0

		Offset += 16;


		Char_Byte FileType = Char_Byte(Output.begin() + Offset, Output.begin() + Offset + 4);

		uint32_t FileTypeNumber = FileType.CastToint32_BE().variable;

		Offset += 4;


		std::string FileTypeString(Output.begin() + Offset, Output.begin() + Offset + FileTypeNumber);

		if (FileTypeString == TextureType) {

			TextureIndex++;

			TempFileName.clear();
			TempFileName.shrink_to_fit();

			TempFileName.append(std::to_string(TextureIndex));
			TempFileName.append("Texture");
			TempFileName.append(".txd");
		}

		else if (FileTypeString == GraphType) {
			TextureIndex++;

			TempFileName.clear();
			TempFileName.shrink_to_fit();

			TempFileName.append(std::to_string(TextureIndex));
			TempFileName.append("Graph");
			TempFileName.append(".graph");
		}

		// file path to output to
		std::filesystem::path FilePath = std::filesystem::path(ExtractedSection) / TempFileName;

		// output file
		std::ofstream TempOutput(FilePath, std::ios::binary);



		int StartOfActualFile = AddOffsetOneDataToMe + OffsetOneData;
		int EndOfActualFile = AddSizeToMe + MemoryOffset.CastToint32_LE().variable;

		std::vector<uint8_t> Input;
		Input.insert(Input.begin(), Output.begin() + StartOfActualFile, Output.begin() + EndOfActualFile);

		WriteSectionToFile(TempOutput, Input);

		Input.clear();
		Input.shrink_to_fit();

		Offset = AddSizeToMe + MemoryOffset.CastToint32_LE().variable;

		TempOutput.close();


	}
	




	

}

void Str_Load_Full::ExtractFiles()
{
	// this is done to load in the section folder, we are not making a new one dw
	std::filesystem::path folder(USFP);

	if (!std::filesystem::exists(folder) || !std::filesystem::is_directory(folder)) {
		return;
	}


	// this will create a new folder to which all extracted files are put into

	if (!std::filesystem::exists(ExtractedSection.c_str())) {
		if (std::filesystem::create_directory(ExtractedSection.c_str())) {
			std::cout << " Created the folder " << " " << ExtractedSection.c_str() << std::endl;
		}

	}

	// gets every file from folder, determins if they are an acceptable file

	for(const auto &entry : std::filesystem::directory_iterator(folder)) {
		if (std::filesystem::is_regular_file(entry)) {  
			std::string TempString = entry.path().string();
			FileNames.push_back(TempString);
		}
	}

	

	for (int i = 0; i < FileNames.size(); i++) {
		ExtractSection(FileNames[i].c_str());
	}
}

void Str_Load_Full::ConvertToTxt()
{

}

void Str_Load_Full::ConvertToStr()
{

}

void Str_Load_Full::destroy()
{

}


