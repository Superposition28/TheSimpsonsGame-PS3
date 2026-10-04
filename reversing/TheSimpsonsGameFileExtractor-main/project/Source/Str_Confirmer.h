#pragma once
#include "Bytes.h"
#include <fstream>
#include <ostream>
#include <iostream>
#include <filesystem>
#include <vector>


class Str_Confirmer {

public:

	Str_Confirmer(){}
	~Str_Confirmer(){}

	void ReadLine(std::string CurrentLine);
	void Init(const char* file);
	int ReadHeader();


private:


	std::vector<unsigned char> Header;

	std::fstream FileObject;
};