using System;
using System.IO;

namespace RWReader.Sections
{
	public class BinMeshPLG : Section
	{
		public BinMeshPLG()
		{
			Name = "Bin Mesh PLG";
			Header.ClumpID = 0x0000050E;
			DataStorageType = SectionDataStorage.DataInSection;
			CanHaveChildren = false;
		}

		public int Flags;
		public int NumMeshes;
		public int IndexCount;
		public MeshData[] Data;

		public override void Deserialize(BinaryReader reader)
		{
			Flags = reader.ReadInt32();
			NumMeshes = reader.ReadInt32();
			IndexCount = reader.ReadInt32();
			Data = new MeshData[NumMeshes];
			for (var i = 0; i < NumMeshes; i++)
			{
				var data = new MeshData();
				data.NumIndices = reader.ReadInt32();
				data.MaterialIndex = reader.ReadInt32();

				/*if (reader.BaseStream.Position != reader.BaseStream.Length)
				{
					data.Indices = new int[data.NumIndices];
					for (var j = 0; j < data.NumIndices; j++)
					{
						data.Indices[j] = reader.ReadInt32();
					}
				}*/

				Data[i] = data;
			}
		}

		public struct MeshData
		{
			public int NumIndices;
			public int MaterialIndex;
			public int[] Indices;
		}
	}
}