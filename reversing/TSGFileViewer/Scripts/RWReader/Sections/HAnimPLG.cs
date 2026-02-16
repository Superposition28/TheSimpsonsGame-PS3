using System;
using System.IO;
using UnityEngine;

namespace RWReader.Sections
{
	[Serializable]
	public class HAnimPLG : Section
	{
		public HAnimPLG()
		{
			Name = "HAnim PLG";
			Header.ClumpID = 0x0000011E;
			DataStorageType = SectionDataStorage.DataInSection;
			CanHaveChildren = false;
		}

		public int HAnimVersion;
		public int NodeID;
		public int NumNodes;

		public override void Deserialize(BinaryReader reader)
		{
			HAnimVersion = reader.ReadInt32();
			NodeID = reader.ReadInt32();
			NumNodes = reader.ReadInt32();

			//Debug.Log($"[HAnim PLG] NodeID: {NodeID}, NumNodes: {NumNodes}");
		}
	}
}