using System;
using System.IO;
using RWReader.RWStructs;
using UnityEngine;
using Color = System.Drawing.Color;
using Vector2 = System.Numerics.Vector2;

namespace RWReader.Sections
{
	[Serializable]
	public class Geometry : Section
	{
		public Geometry()
		{
			Name = "Geometry";
			Header.ClumpID = 0x0000000F;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int Format;
		public int NumTexSets;
		public int NumTriangles;
		public int NumVertices;
		public int NumMorphTargets;

		public float Ambient;
		public float Specular;
		public float Diffuse;

		public Color[] PreLitColors;
		public Vector2[,] TexCoords;

		public MorphTargetInfo[] MorphTargetInfos;

		public override void Deserialize(BinaryReader reader)
		{
			Format = reader.ReadInt32();
			NumTexSets = (Format & 0x00FF0000) >> 16;
			NumTriangles = reader.ReadInt32();
			NumVertices = reader.ReadInt32();
			NumMorphTargets = reader.ReadInt32();
			//Debug.Log($"[Geometry] NumTriangles: {NumTriangles}, NumVertices: {NumVertices}, NumMorphTargets:{NumMorphTargets}");

			if (Header.LibraryID.Version < 0x34000)
			{
				Ambient = reader.ReadSingle();
				Specular = reader.ReadSingle();
				Diffuse = reader.ReadSingle();
			}

			/*if ((Format & (int)GeometryType.Native) == 0)
			{
				if ((Format & (int)GeometryType.PreLit) != 0)
				{
					PreLitColors = new Color[NumVertices];
					for (var i = 0; i < NumVertices; i++)
					{
						PreLitColors[i] = reader.ReadRwRGBA();
					}
				}

				TexCoords = new Vector2[NumTexSets, NumVertices];

				for (var i = 0; i < NumTexSets; i++)
				{
					for (var j = 0; j < NumVertices; j++)
					{
						TexCoords[i, j] = new Vector2(reader.ReadSingle(), reader.ReadSingle());
					}
				}

				// TODO : triangles
			}*/

			MorphTargetInfos = new MorphTargetInfo[NumMorphTargets];
			for (var i = 0; i < NumMorphTargets; i++)
			{
				var targetInfo = new MorphTargetInfo();

				targetInfo.BoundingSphere = reader.ReadRwSphere();
				targetInfo.HasVertices = reader.ReadBool32();
				targetInfo.HasNormals = reader.ReadBool32();
				if (targetInfo.HasVertices)
				{
					//TODO : implement
				}

				if (targetInfo.HasNormals)
				{
					//TODO : implement
				}

				MorphTargetInfos[i] = targetInfo;
			}
		}

		public bool IsFlagSet(GeometryType flag) => (Format & (int)flag) != 0;

		[Flags]
		public enum GeometryType
		{
			TriangleStrip = 0x1,
			Positions = 0x2,
			Textured = 0x4,
			PreLit = 0x8,
			Normals = 0x10,
			Light = 0x20,
			ModulateMaterialColor = 0x40,
			Textured2 = 0x80,
			Native = 0x1000000
		}
	}
}