#include "Str_Confirmer.h"


void Str_Confirmer::Init(const char* file) {
	char* Filename = (char*)file;

	std::ifstream EntireFile(Filename, std::ios::binary);
	if (!EntireFile.is_open()) {
		std::cerr << "Cannot open file: " << Filename << "\n";
		return;
	}



	constexpr std::streamsize ReadSize = 2048;
	std::vector<char> buffer(ReadSize);

	if (!EntireFile.read(buffer.data(), ReadSize)) {
		std::cerr << "Failed to read file content.\n";
		return;
	}

	EntireFile.close();

	for (char ch : buffer) {
		ReadLine(std::string(1, ch));
	}

	std::cout << "Completed the Init " << buffer.size() << " Is the Buffer Size\n";


}

void Str_Confirmer::ReadLine(std::string CurrentLine)
{
	int Size = CurrentLine.size();

	for (int j = 0; j < Size; j++) {

		Header.push_back(CurrentLine[j]);



	}
}

int Str_Confirmer::ReadHeader() {
	int Offset = 12;
	int GlobalOffset = Char_Byte(Header.begin(), Offset, 4).CastToint32_BE().variable;

	if (GlobalOffset > 0) {
		return 1;
	}

	else {
		return 0;
	}
}
