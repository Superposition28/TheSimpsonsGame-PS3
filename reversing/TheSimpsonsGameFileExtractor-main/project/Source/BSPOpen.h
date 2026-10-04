#pragma once
#include <iostream>
#include <fstream>
#include <ostream>
#include <string>
#include <vector>
#include "Bytes.h"
#include <filesystem>



struct BSP_Node_Header {

	// x,y and z for the first point, these are big endian float 32s btw

	float First;
	float Second;
	float Third;

	// this is just padding, or it denotes the 0x0000008F flag
	int Fourth;

	// x,y and z for the Second point, these are big endian float 32s btw
	float Fifth;
	float Sixth;
	float Seventh;

	// either just padding OR one of those 0x00008F termination checks, i think these are done to assertain the depth of the tree
	int Eighth;
	
	// the 9th byte is the parent node offset, use that to go back up
	// the 10th byte, is an offset to the next child LEFT node
	// the 11th byte, is an offset, to the next child RIGHT node

	int Ninth;
	int Tenth;
	int Eleventh;

	// there are 12 more bytes i need to fill out, the second to last or last i forget is either ox80 or 0x81 denoting a final end point
	// to that node, like a final leaf node, yes i checked

	int Twelfth;

	// 0x0000FFFF
	int Thirteen;

	// just full of FF's i.e 0xFFFFFFFF
	int Fourteen;

	// either 0x80 or 0x81, i think 81 is either end leaf node OR denotes when the eactual geometry is done, but i dont know
	int Fifteen;

	//padding 
	int Sixteen;

};


class BSPNode {
public:

	BSPNode() {};
	~BSPNode() {};

public:

	BSPNode* Parent;
	BSPNode* LeftChild;
	BSPNode* RightChild;

	BSP_Node_Header Info;
};

class BSPOpen {
public:
	BSPOpen() {}

	BSPOpen(std::string _name)
	{
		Name = _name;
	}




	void Init();
	void ProcessLines(std::string Line, std::vector<unsigned char>& _Characters);
	void ReadHeader();
	void RecursiveTreeBuilder(BSPNode * Node, int& counter, int& leafcounter); 
    void RecursiveLeafFinder(std::vector<BSPNode>& LeafNodes, BSPNode* Node);
	void ExtraData();
	void ConvertToObj();
	void WriteToFile();

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


public:

	int GlobalFileIndex = -1;

	std::vector<uint8_t> OutputVector;


	std::string FilePath;





private:
	int GlobalFileOffset;

	std::fstream FileObject;

	std::string Name;

	std::vector<unsigned char> Characters;

	// we can use this as an exit condition
	int ObjectCount = 0;

	int AmountOfCharacters;

	int IndexOfSubGeometry = 0;

	std::vector<uint8_t> Geometry;

	// list of triangles, each sublist will have 3 points

	std::vector < Vector3> Normals;
	std::vector < Vector3> Vertices;
	std::vector < Vector2> UVs;

	std::vector< std::vector<int>> Indexes;


	BSPNode* FirstNode = nullptr;

};