using System;
using System.IO;

namespace RWReader.Sections
{
	[Serializable]
	public class MaterialList : Section
	{
		public MaterialList()
		{
			Name = "Material List";
			Header.ClumpID = 0x00000008;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int MaterialCount;
		public int[] MaterialIndexes;

		public override void Deserialize(BinaryReader reader)
		{
			MaterialCount = reader.ReadInt32();

			MaterialIndexes = new int[MaterialCount];

			for (var i = 0; i < MaterialCount; i++)
			{
				MaterialIndexes[i] = reader.ReadInt32();
			}
		}

		public Material[] GetMaterials()
		{
			var materials = GetChildren<Material>();

			var resultMaterials = new Material[MaterialCount];

			for (int i = 0; i < MaterialCount; i++)
			{
				var index = MaterialIndexes[i];

				if (index == -1)
				{
					resultMaterials[i] = materials[i];
				}
				else
				{
					resultMaterials[i] = materials[index];
				}
			}

			return resultMaterials;
		}
	}
}