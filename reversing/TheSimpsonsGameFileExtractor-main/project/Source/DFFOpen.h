#pragma once
#include <iostream>
#include <fstream>
#include <ostream>
#include <string>
#include <vector>
#include "Bytes.h"
#include <filesystem>


class DFFOpen {

public:

	DFFOpen() {}

	DFFOpen(std::string _name)
	{
		Name = _name;
	}




	void Init();
	void ProcessLines(std::string Line, std::vector<unsigned char>& _Characters);
	void ExtractData();
	void ConvertToObj(std::vector<uint8_t> InputData, int VertexCount, int FaceCount, int _Offset);
	bool ProcessData(int _ObjectAmount);
	void WriteToFile();




public:

	std::vector<uint8_t> OutputVector;


	std::string FilePath;

	// the whole purpose of this, is to make it impossible to have repeating files, no matter what
	int GlobalFileIndex = -1;


private:

	std::vector<std::vector<int>> CastStripToFace(std::vector<int> _Strip) {


		bool Flip = false;
		std::vector<std::vector<int>> Output;

		for (int i = 0; i < _Strip.size() - 2; i++) {
			if (Flip) {
				Output.push_back(std::vector<int>{_Strip[i + 2], _Strip[i + 1], _Strip[i]});
			}

			else {
				Output.push_back(std::vector<int>{_Strip[i + 1], _Strip[i + 2], _Strip[i]});
			}

			Flip = !Flip;
		}


		return Output;
	}

private:

	int GlobalFileOffset;

	std::fstream FileObject;

	std::string Name;

	std::vector<unsigned char> Characters;

	// we can use this as an exit condition
	int ObjectCount = 0;



	int AmountOfCharacters;

	int SizeOfFile;
	int FaceAmount;
	int IndexAmount;
	int VertexAmount;

	int IndexOffsetForSubMeshes = 0;

	bool HasSkin = false;

	std::vector<uint8_t> GeometryList;

	std::vector<uint8_t> Geometry;

	// list of triangles, each sublist will have 3 points

	std::vector < Vector3> Normals;
	std::vector < Vector3> Vertices;
	std::vector < Vector2> UVs;

	std::vector< std::vector<int>> Indexes;




};