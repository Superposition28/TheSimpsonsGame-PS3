#include "RWSOpen.h"

void RwsOpen::Init()
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

void RwsOpen::ProcessLines(std::string Line, std::vector<unsigned char>& _Characters)
{
	int Length = Line.size();

	for (int i = 0; i < Length; i++) {
		_Characters.push_back(Line[i]);
		AmountOfCharacters += 1;

	}
}

void RwsOpen::ExtractData()
{

	int ClumpId = 16;
	std::vector<int> ChunkIds = { 14, 20, 26 , 7, 3 };
	std::vector<int> StructIds = {1,286, 2, 59925, 59926, 59955, 1294, 59923};

	bool FoundGeometry = false;
	bool InChunk = false;

	int Offset = 0;

	int GeometryTypeId = 26;


	// fuck it make this bitch recursive, iknow you can, thsi isnt hard

	Chunk GetChunk = Chunk(Characters.begin(), Offset);

	Chunk StructureCheck = Chunk(Characters.begin(), Offset);


	ObjectCount = Char_Byte(Characters.begin(), Offset, 4).CastToint32_LE().variable;
	Offset -= 4;

	if (StructureCheck.type == 1) {
		Offset += StructureCheck.size;
	}

	bool Exit = false;

	if (ObjectCount > 1) {
		int gfh = 0;
	}

	while (!Exit) {
		GetChunk = Chunk(Characters.begin(), Offset);

		for (int i = 0; i < ChunkIds.size(); i++) {
			if (ChunkIds[i] == GetChunk.type && !(GetChunk.type == GeometryTypeId)) {
				InChunk = true;
			}

			else if (ChunkIds[i] == GetChunk.type && GetChunk.type == GeometryTypeId) {
				GeometryList.insert(GeometryList.begin(), Characters.begin() + Offset, Characters.begin() + Offset + GetChunk.size);
				GlobalFileOffset += Offset;
				Exit = ProcessData(ObjectCount);
				break;
			}
		}

		

		for (int i = 0; i < StructIds.size(); i++) {
			if (StructIds[i] == GetChunk.type) {
				Offset += GetChunk.size;
				InChunk = false;
			}
			
		}
		
		
	}
}


bool RwsOpen::ProcessData(int _ObjectCount) {

	int ObjectCount = _ObjectCount;

	int Offset = 0;

	int LocalOffset = GlobalFileOffset;

	


	// i need to make this very clear, this is a terrible way of doing it, im just doing it this way because they all follow the same file format so screw it
	// yes im aware jan this is dumb, i should have a id list and a struct lsit and just go down recursively through the hierachy, this is just easier

	// this is the beginner struct
	Chunk Struct = Chunk(GeometryList.begin(), Offset);


	std::vector<uint8_t> StructSum = Struct.Process(GeometryList, Offset);

	while (ObjectCount > 0) {
		ObjectCount--;

		bool HasTripSet = false;
		bool HasTextures = false;
		bool HasGeometryPositions = false;
		bool HasPreLitGeometry = false;
		bool HasGeometryNormals = false;
		bool HasModulatedMaterial = false;
		bool HasTextures2 = false;

		bool HasGeometryLight = false;

		int VertexCount = 0;
		int FaceCount = 0;
		int IndexCount = 0;
		int UnknownCount = 0;


		Chunk GeometryListChunk = Chunk(GeometryList.begin(), Offset);



		Chunk GeometryStruct = Chunk(GeometryList.begin(), Offset);


		int GeometryStructSumOffset = 0;
		std::vector<uint8_t> GeometryStructSum = GeometryStruct.Process(GeometryList, Offset);


		// please extract data now


		std::bitset<8> Flags(GeometryStructSum[0]);

		HasTripSet = Flags[0];
		HasGeometryPositions = Flags[1];
		HasTextures = Flags[2];
		HasPreLitGeometry = Flags[3];
		HasGeometryNormals = Flags[4];

		HasGeometryLight = Flags[5];
		HasModulatedMaterial = Flags[6];
		HasTextures2 = Flags[7];

		GeometryStructSumOffset += 2;



		UnknownCount = Char_Byte(GeometryStructSum.begin(), GeometryStructSumOffset, 2).CastToint16_LE().variable;
		FaceCount = Char_Byte(GeometryStructSum.begin(), GeometryStructSumOffset, 4).CastToint32_LE().variable;
		VertexCount = Char_Byte(GeometryStructSum.begin(), GeometryStructSumOffset, 4).CastToint32_LE().variable;



		Chunk MaterialList = Chunk(GeometryList.begin(), Offset);


		Offset += MaterialList.size;

		Chunk ExtensionGeometry = Chunk(GeometryList.begin(), Offset);



		Chunk ExtentsionGeometryStruct = Chunk(GeometryList.begin(), Offset);

		std::vector<uint8_t> GeometruStructOutput = ExtentsionGeometryStruct.Process(GeometryList, Offset);

		int GeometryStructOffset = 0;

		int FaceType = Char_Byte(GeometruStructOutput.begin(), GeometryStructOffset, 4).CastToint32_LE().variable;
		int SplitCount = Char_Byte(GeometruStructOutput.begin(), GeometryStructOffset, 4).CastToint32_LE().variable;
		IndexCount = Char_Byte(GeometruStructOutput.begin(), GeometryStructOffset, 4).CastToint32_LE().variable;

		Chunk Unknown1 = Chunk(GeometryList.begin(), Offset);

		std::vector<uint8_t> Unknwon1Struct = Unknown1.Process(GeometryList, Offset);

		Chunk Unknown2 = Chunk(GeometryList.begin(), Offset);



		std::vector<uint8_t> Unknwon2Struct = Unknown2.Process(GeometryList, Offset);

		Chunk ACTUALGEOMETRY = Chunk(GeometryList.begin(), Offset);


		Geometry = ACTUALGEOMETRY.Process(GeometryList, Offset);

		GlobalFileOffset = LocalOffset + (Offset - ACTUALGEOMETRY.size);


		ConvertToObj(Characters, VertexCount, FaceCount, GlobalFileOffset);

	}

	
	WriteToFile();

	return true;



}

void RwsOpen::WriteToFile()
{
	std::string name("Output");


	GlobalFileIndex++;
	name.append(std::to_string(GlobalFileIndex));
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


void RwsOpen::ConvertToObj(std::vector<uint8_t> InputData, int VertexCount, int FaceCount, int _Offset)
{
	

	// local offset for only the input data
	int Offset = _Offset;


	// this number is unknown, but we need to do this to skip 4 bytes
	int UselessNumber = Char_Byte(InputData.begin(), Offset, 4).CastToint32_LE().variable;

	// this should be 848, this is our offset to get to faces
	int FaceOffset = Char_Byte(InputData.begin(), Offset, 4).CastToint32_LE().variable;


	// this is the size of the ACTUAL geometry data
	int MeshDataSize = Char_Byte(InputData.begin(), Offset, 4).CastToint32_LE().variable;


	int MeshDataStart = Offset;

	// we do this to skip 20
	Offset += 20;

	// amount of tables, should be 23
	int TableCount = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable;


	//amount of subtables, should be 1, because only 1 mesh
	int SubTableCount = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable;



	std::vector<int> DataOffsets;


	// we get ALL of the offsets per table, and we skip 4 each time we do so
	for (int i = 0; i < TableCount; i++) {
		Offset += 4;
		DataOffsets.push_back(Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable);
	}


	// start of the data
	int DataSubStart = Offset;










	// goes through each sub table, depends on mesh
	for (int i = 0; i < SubTableCount; i++) {

		

	

		

		Offset = DataSubStart + (i * 0xc) + 8;

		int NewOffset = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable;

		Offset = NewOffset + MeshDataStart + 0xC;

		int VertCountDataOffset = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable + MeshDataStart;

		Offset = VertCountDataOffset;

		int VertChunkTotalSize = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable;

		int VertChunkSize = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable;

		int VertCount = int(VertChunkTotalSize / VertChunkSize);

		Offset += 8;

		int VertexStart = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable + FaceOffset + MeshDataStart;

		Offset += 0x14;

		int FaceCount = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable;

		FaceCount /= 2;

		Offset += 4;

		int FaceStart = Char_Byte(InputData.begin(), Offset, 4).CastToint32_BE().variable + FaceOffset + MeshDataStart;


		Offset = FaceStart;

		std::vector<std::vector<int>> StripList;

		std::vector<int> TempList;

		for (int j = 0; j < FaceCount; j++) {
			int Indice = Char_Byte(InputData.begin(), Offset, 2).CastToUint16_BE().variable;

			
			
		
			//max uint16 size
			if (Indice == 65535) {
				StripList.push_back(TempList);
				TempList.clear();
			}

			else {
				TempList.push_back(Indice);
			}

			
		}



		std::vector<std::vector<int>> FaceList;

		for (int j = 0; j < StripList.size(); j++) {

			for (int k = 0; k < CastStripToFace(StripList[j]).size(); k++) {

				std::vector<int> Temp = CastStripToFace(StripList[j])[k];

				FaceList.push_back(Temp);
			}
		}


		std::vector<Vector3> VerticesTable;
		std::vector<Vector2> UVTable;


		for (int j = 0; j < VertCount; j++) {
			Offset = VertexStart + j * VertChunkSize;

			// this is for Vector3

			//Vector3 TempVert = Char_Byte(InputData.begin(), Offset, 12).CastToVector3_BE();


			float V0 = Char_Byte(InputData.begin(), Offset, 4).CastTo32Float_BE();
			float V1 = Char_Byte(InputData.begin(), Offset, 4).CastTo32Float_BE();
			float V2 = Char_Byte(InputData.begin(), Offset, 4).CastTo32Float_BE();





			VerticesTable.push_back(Vector3(V0, V1, V2));

			Offset = VertexStart + j * VertChunkSize + VertChunkSize - 8;



			float UV1 = Char_Byte(InputData.begin(), Offset, 4).CastTo32Float_BE();
			float UV2 = 1 - Char_Byte(InputData.begin(), Offset, 4).CastTo32Float_BE();



			UVTable.push_back(Vector2(UV1, UV2));

		}



		for (int v = 0; v < VerticesTable.size(); v++) {
			Vertices.push_back(VerticesTable[v]);
			UVs.push_back(UVTable[v]);
		}

		//Vertices = VerticesTable;
		//UVs = UVTable;



		std::vector<Vector3> NormalTable;
		NormalTable.resize(VerticesTable.size(), Vector3(0, 0, 0));

		for (int Triangle = 0; Triangle < FaceList.size(); Triangle++) {

			Vector3 Vert0 = VerticesTable[FaceList[Triangle][0]];
			Vector3 Vert1 = VerticesTable[FaceList[Triangle][1]];
			Vector3 Vert2 = VerticesTable[FaceList[Triangle][2]];

			// face normal

			Vector3 AB = Vert1 - Vert0;
			Vector3 AC = Vert2 - Vert0;

			Vector3 CrossProduct = Vector3::Cross(AB, AC);

			Vector3 Normal = CrossProduct;

			for (int b = 0; b < 3; b++) {
				int VertexIndex = FaceList[Triangle][b];
				NormalTable[VertexIndex] += Normal;

			}

		}

		for (int v = 0; v < NormalTable.size(); v++) {

			float magnitude = NormalTable[v].GetMagntitude();
			if (magnitude > 0.0f) {
				NormalTable[v] /= magnitude;
			}
			else {
				
				NormalTable[v] = Vector3(0, 0, 1);
			}
			Normals.push_back(NormalTable[v]);
		}

		for (int v = 0; v < FaceList.size(); v++) {
			FaceList[v][0] = FaceList[v][0] + 1 + IndexOffsetForSubMeshes;
			FaceList[v][1] = FaceList[v][1] + 1 + IndexOffsetForSubMeshes;
			FaceList[v][2] = FaceList[v][2] + 1 + IndexOffsetForSubMeshes;
			Indexes.push_back(FaceList[v]);
		}

		IndexOffsetForSubMeshes += VerticesTable.size();


		//Indexes = FaceList;
		

	}


}
