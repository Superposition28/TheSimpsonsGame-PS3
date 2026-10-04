#include "BSPOpen.h"

void BSPOpen::Init()
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

void BSPOpen::ProcessLines(std::string Line, std::vector<unsigned char>& _Characters)
{
	int Length = Line.size();

	for (int i = 0; i < Length; i++) {
		_Characters.push_back(Line[i]);
		AmountOfCharacters += 1;

	}
}

void BSPOpen::ReadHeader()
{
	int Offset = 0;

	int Identifier = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;
	int BlankNumber = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;
	int AmountOfSections = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;
	int StartOfSectionsInHeader = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	int BlankNumber2 = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	int UnKnown = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;
	int UnKnown2 = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;
	int UnKnown3 = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;
	int UnKnown4 = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	int BlankNumber3 = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// takes us to the first node :D
	int FirstOffset = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// i believe these are the uv data, im just saying
	int UVsOffset = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// padding
	int UVPadding = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// then these are the uv dictionary offset
	int UVDictionary = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// actual uvs indexes

	int UVIndexes = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// mesh data, i believe

	int MeshOffset = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// mesh padding 
	int MeshPadding = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// mesh dictionary 

	int MeshDictionary = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	// mesh indexes 

	int MeshIndexes = Char_Byte(Characters.begin(), Offset, 4).CastToint32_BE().variable;

	BSP_Node_Header FirstNodeInformation = BSP_Node_Header
	{
		FirstNodeInformation.First = Char_Byte(Characters.begin(), FirstOffset, 4).CastTo32Float_BE(),
		FirstNodeInformation.Second = Char_Byte(Characters.begin(), FirstOffset, 4).CastTo32Float_BE(),
		FirstNodeInformation.Third = Char_Byte(Characters.begin(), FirstOffset, 4).CastTo32Float_BE(),
		FirstNodeInformation.Fourth = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable,
		FirstNodeInformation.Fifth = Char_Byte(Characters.begin(), FirstOffset, 4).CastTo32Float_BE(),
		FirstNodeInformation.Sixth = Char_Byte(Characters.begin(), FirstOffset, 4).CastTo32Float_BE(),
		FirstNodeInformation.Seventh = Char_Byte(Characters.begin(), FirstOffset, 4).CastTo32Float_BE(),
		FirstNodeInformation.Eighth = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable,
		FirstNodeInformation.Ninth = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable,
		FirstNodeInformation.Tenth = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable,
		FirstNodeInformation.Eleventh = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable,
		FirstNodeInformation.Twelfth = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable,
		FirstNodeInformation.Thirteen = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable,
		FirstNodeInformation.Fourteen = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable,
		FirstNodeInformation.Fifteen = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_LE().variable,
		FirstNodeInformation.Sixteen = Char_Byte(Characters.begin(), FirstOffset, 4).CastToint32_BE().variable

	};

	FirstNode = new BSPNode();
	FirstNode->Info = FirstNodeInformation;

	int counter = 0;
	int leafcounter = 0;

	std::vector<BSPNode> LeafNodes;

	RecursiveTreeBuilder(FirstNode, counter, leafcounter);

	RecursiveLeafFinder(LeafNodes, FirstNode);

	

	Offset = MeshOffset;


	std::vector<std::vector<int>> FaceIndexes;

	std::vector<Vector3> VerticesTable;
	std::vector<Vector2> UvTable;

	for (int i = MeshOffset; i < MeshPadding; i+= 16)
	{
		float x = Char_Byte(Characters.begin(), Offset, 4).CastTo32Float_BE();
		float y = Char_Byte(Characters.begin(), Offset, 4).CastTo32Float_BE();
		float z = Char_Byte(Characters.begin(), Offset, 4).CastTo32Float_BE();
		float terminationClause = Char_Byte(Characters.begin(), Offset, 4).CastTo32Float_BE();


		UvTable.push_back(Vector2(0, 0));



		Vector3 TempVert = Vector3{ x,y,z };
		VerticesTable.push_back(TempVert);
	}

	
	
	Offset = MeshDictionary;
	Offset += 4;

	int StartMeshDictionary = MeshIndexes - Offset;
	// this is the mesh dictionary
	for (int i = 0; i < StartMeshDictionary - 8; i+=8) {

		// this number is the start of the actual index data, also move it 4 because its 8 byte blocked
		int DictionaryOffset = Char_Byte(Characters.begin(), Offset,4).CastToint32_BE().variable;
		Offset += 4;

		// this is done so we can look for the end, without screwing it up
		
		int tempOffset = Offset;

		// this is the actual ending, using the fake offset, so our normal offset isnt broken

		int DictionaryOffsetEnding = Char_Byte(Characters.begin(), tempOffset, 4).CastToint32_BE().variable;

		int TempOffset = DictionaryOffset;

		std::vector<int> TriangleStripIndexes;

		for (int j = DictionaryOffset; j < DictionaryOffsetEnding; j+=2) {
			int index = Char_Byte(Characters.begin(), TempOffset, 2).CastToUint16_BE().variable + 1 + IndexOfSubGeometry;
			TriangleStripIndexes.push_back(index);
		}

		IndexOfSubGeometry += TriangleStripIndexes.size();
		FaceIndexes.push_back(TriangleStripIndexes);


	}



	std::vector<std::vector<int>> FaceList;


	for (int j = 0; j < FaceIndexes.size(); j++) {

		for (int k = 0; k < CastStripToFace(FaceIndexes[j]).size(); k++) {
		    std::vector<int> Temp = CastStripToFace(FaceIndexes[j])[k];
			FaceList.push_back(Temp);
		}
	}



	
	UVs = UvTable;
	Vertices = VerticesTable;
	Normals = std::vector<Vector3>(VerticesTable.size());
	Indexes = FaceList;

	

	WriteToFile();

}


// what does node at first look like
void BSPOpen::RecursiveTreeBuilder(BSPNode* Node, int &counter, int &leafcounter)
{
	int OffsetToLeftChild = Node->Info.Tenth;
	int OffsetToRightChild = Node->Info.Eleventh;


	// xyz
	// padding
	// xyz
	// padding
	// parent
	// left node offset
	// right node offset
	// 

	BSP_Node_Header LeftInfo = BSP_Node_Header
	{
		LeftInfo.First = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastTo32Float_BE(),
		LeftInfo.Second = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastTo32Float_BE(),
		LeftInfo.Third = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastTo32Float_BE(),
		LeftInfo.Fourth = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable,
		LeftInfo.Fifth = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastTo32Float_BE(),
		LeftInfo.Sixth = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastTo32Float_BE(),
		LeftInfo.Seventh = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastTo32Float_BE(),
		LeftInfo.Eighth = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable,

		LeftInfo.Ninth = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable,
		LeftInfo.Tenth = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable,
		LeftInfo.Eleventh = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable,

		LeftInfo.Twelfth = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable,
		LeftInfo.Thirteen = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable,
		LeftInfo.Fourteen = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable,

		LeftInfo.Fifteen = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_LE().variable,

	    LeftInfo.Sixteen = Char_Byte(Characters.begin(), OffsetToLeftChild, 4).CastToint32_BE().variable

	};

	BSP_Node_Header RightInfo = BSP_Node_Header
	{
		RightInfo.First = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastTo32Float_BE(),
		RightInfo.Second = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastTo32Float_BE(),
		RightInfo.Third = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastTo32Float_BE(),
		RightInfo.Fourth = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable,
		RightInfo.Fifth = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastTo32Float_BE(),
		RightInfo.Sixth = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastTo32Float_BE(),
		RightInfo.Seventh = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastTo32Float_BE(),
		RightInfo.Eighth = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable,

		RightInfo.Ninth = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable,
		RightInfo.Tenth = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable,
		RightInfo.Eleventh = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable,

		RightInfo.Twelfth = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable,
		RightInfo.Thirteen = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable,
		RightInfo.Fourteen = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable,

		RightInfo.Fifteen = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_LE().variable,

		RightInfo.Sixteen = Char_Byte(Characters.begin(), OffsetToRightChild, 4).CastToint32_BE().variable
	};





	BSPNode* LeftNode = new BSPNode();
	BSPNode* RightNode = new BSPNode();

	LeftNode->Info = LeftInfo;
	RightNode->Info = RightInfo;

	LeftNode->Parent = Node;
	RightNode->Parent = Node;


	// we do this to exclude false info for the last leaf nodes
	if (!(Node->Info.Tenth <= 0)) {
		Node->LeftChild = LeftNode;
	}

	

	if (!(Node->Info.Eleventh <= 0)) {
		Node->RightChild = RightNode;
	}


	// does node even have a left node we can do down on, and also is it a leaf node via 129

	if (Node->Info.Fifteen == 129) {
		leafcounter++;
	}

	if (!(Node->Info.Tenth <= 0) && Node->Info.Fifteen != 129) {
		counter++;
		
		RecursiveTreeBuilder(LeftNode, counter, leafcounter);
	}



	// does node even have a right node we can do down on, and also is it a leaf node via 129
	
	if (!(Node->Info.Eleventh <= 0) && Node->Info.Fifteen != 129) {
		counter++;

		RecursiveTreeBuilder(RightNode, counter, leafcounter);
	}
	
}

void BSPOpen::RecursiveLeafFinder(std::vector<BSPNode> &LeafNodes, BSPNode* Node)
{
	int IsLeaf = Node->Info.Fifteen;

	if (IsLeaf != 128)
	{
		LeafNodes.push_back(*Node);
		return;
	
	}

	if (Node->LeftChild) {
		RecursiveLeafFinder(LeafNodes, Node->LeftChild);
	}

	if (Node->RightChild) {
		RecursiveLeafFinder(LeafNodes, Node->RightChild);
	}

	
	
}

void BSPOpen::ExtraData()
{

}

void BSPOpen::ConvertToObj()
{

}

void BSPOpen::WriteToFile()
{

	std::string name("Output");
	name.append(std::to_string(1));
	name.append(".obj");

	std::filesystem::path OutputPath = std::filesystem::path(FilePath) / name;

	std::ofstream Output(OutputPath);




	for (size_t i = 0; i < Vertices.size(); i++) {

		std::string Line = "v " + std::to_string(Vertices[i].X) +
			" " + std::to_string(Vertices[i].Y) +
			" " + std::to_string(Vertices[i].Z) +
			"\n";

		OutputVector.insert(OutputVector.end(), Line.begin(), Line.end());
	}

	for (size_t i = 0; i < UVs.size(); i++) {
		std::string Line = "vt " + std::to_string(UVs[i].X) +
			" " + std::to_string(UVs[i].Y) +
			"\n";

		OutputVector.insert(OutputVector.end(), Line.begin(), Line.end());
	}


	for (size_t i = 0; i < Normals.size(); i++) {
		std::string Line = "vn " + std::to_string(Normals[i].X) +
			" " + std::to_string(Normals[i].Y) +
			" " + std::to_string(Normals[i].Z) +
			"\n";
		OutputVector.insert(OutputVector.end(), Line.begin(), Line.end());
	}

	for (size_t i = 0; i < Indexes.size(); i++) {



		std::string Line = "f " + std::to_string(Indexes[i][0]) + "/" + std::to_string(Indexes[i][0]) + "/" + std::to_string(Indexes[i][0]) + " "
			+ std::to_string(Indexes[i][1]) + "/" + std::to_string(Indexes[i][1]) + "/" + std::to_string(Indexes[i][1]) + " "
			+ std::to_string(Indexes[i][2]) + "/" + std::to_string(Indexes[i][2]) + "/" + std::to_string(Indexes[i][2]) + " " + "\n";


		OutputVector.insert(OutputVector.end(), Line.begin(), Line.end());
	}


	if (!Output.is_open()) {
		return;
	}

	if (!OutputVector.empty()) {
		Output.write((const char*)(OutputVector.data()), OutputVector.size());
	}
}
