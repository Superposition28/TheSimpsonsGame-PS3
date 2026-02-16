using System;
using System.IO;
using UnityEngine;

namespace RWReader.Sections
{
	[Serializable]
	public class SkinPLG : Section
	{
		public SkinPLG()
		{
			Name = "Skin PLG";
			Header.ClumpID = 0x00000116;
			DataStorageType = SectionDataStorage.DataInSection;
			CanHaveChildren = false;
		}

		public int NumBones; // Overall number of bones in the skeleton.
		public int NumUsedBones; // Number of bones affected by the skin.
		public int MaxVertexWeights; // Maximum number of non-zero weights per vertex.

		public int[] BoneIndexes; // A list of bone indices, that are affected by the skin.
		public int[][] VertexBoneMapping; // A list that maps all vertices to (up to) four bones of the skeleton.
		public float[][] WeightList; // A list that weights each vertex-bone mapping.
		public UnityEngine.Matrix4x4[] SkinToBoneMatrix; // // Skin-to-Bone transform.

		public override void Deserialize(BinaryReader reader)
		{
			var geometry = GetParent<Geometry>();

			NumBones = reader.ReadByte();
			NumUsedBones = reader.ReadByte();
			MaxVertexWeights = reader.ReadByte();
			//Debug.Log($"[Skin PLG] NumBones: {NumBones}, NumUsedBones:{NumUsedBones}, MaxVertexWeights:{MaxVertexWeights}");
			reader.ReadByte(); // padding

			BoneIndexes = new int[NumUsedBones];
			for (var i = 0; i < NumUsedBones; i++)
			{
				BoneIndexes[i] = reader.ReadByte();
				//Debug.Log($"[Skin PLG] BoneIndex {i} is {BoneIndexes[i]}");
			}

			var numVertices = geometry.NumVertices;

			VertexBoneMapping = new int[numVertices][];
			for (var i = 0; i < numVertices; i++)
			{
				var bones = new int[4];

				for (var j = 0; j < 4; j++)
				{
					bones[j] = reader.ReadByte();
				}

				VertexBoneMapping[i] = bones;
			}

			WeightList = new float[numVertices][];
			for (var i = 0; i < numVertices; i++)
			{
				var values = new float[4];

				for (var j = 0; j < 4; j++)
				{
					values[j] = reader.ReadSingle();
				}

				WeightList[i] = values;
			}

			SkinToBoneMatrix = new UnityEngine.Matrix4x4[NumBones];
			for (var i = 0; i < NumBones; i++)
			{
				var mat = new UnityEngine.Matrix4x4();
				// TODO : should this be row or column????
				mat.SetRow(0, new UnityEngine.Vector4(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle()));
				mat.SetRow(1, new UnityEngine.Vector4(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle()));
				mat.SetRow(2, new UnityEngine.Vector4(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle()));
				mat.SetRow(3, new UnityEngine.Vector4(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle()));
				SkinToBoneMatrix[i] = mat;
			}

			var boneLimit = reader.ReadUInt32();
			var numGroups = reader.ReadUInt32();
			var numRemaps = reader.ReadUInt32();
			//Debug.Log($"[Skin PLG] BoneLimit: {boneLimit}, NumGroups: {numGroups}, NumRemaps: {numRemaps}");
		}
	}
}