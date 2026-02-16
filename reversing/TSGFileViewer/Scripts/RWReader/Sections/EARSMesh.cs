using System;
using System.Collections.Generic;
using System.IO;
using RWReader.RWStructs;
using UnityEngine;

namespace RWReader.Sections
{
	[Serializable]
	public class EARSMesh : Section
	{
		public EARSMesh()
		{
			Name = "EARS Mesh";
			Header.ClumpID = 0x0000EA33;
			DataStorageType = SectionDataStorage.DataInSection;
			CanHaveChildren = false;
		}

		public SubmeshHeader[] SubmeshHeaders;
		public SubmeshInfo[] SubmeshInfos;

		public override void Deserialize(BinaryReader reader)
		{
			reader.ReadBytes(20);
			var dataBlockOffset = reader.ReadUInt32BigEndian();
			var dataBlockSize = reader.ReadUInt32BigEndian();
			reader.ReadBytes(4);
			var tableEntryCount = reader.ReadUInt32BigEndian();
			var submeshCount = reader.ReadUInt32BigEndian();

			for (var i = 0; i < tableEntryCount; i++)
			{
				reader.ReadBytes(8);
			}

			SubmeshHeaders = new SubmeshHeader[submeshCount];
			for (var i = 0; i < submeshCount; i++)
			{
				reader.ReadBytes(4); // Skip constant
				SubmeshHeaders[i] = new SubmeshHeader
				{
					SubmeshInfoBlockSize = reader.ReadUInt32BigEndian(),
					SubmeshInfoBlockOffset = reader.ReadUInt32BigEndian()
				};
			}

			SubmeshInfos = new SubmeshInfo[submeshCount];
			for (var i = 0; i < submeshCount; i++)
			{
				reader.BaseStream.Position = SubmeshHeaders[i].SubmeshInfoBlockOffset + 12;

				reader.ReadBytes(4);
				var info = new SubmeshInfo();
				info.ShaderHash = reader.ReadUInt32BigEndian();
				info.Unk0 = reader.ReadUInt32BigEndian(); //reader.ReadBytes(4);
				var mddbOffset = reader.ReadUInt32BigEndian();
				info.MatrialSplitCount = reader.ReadUInt32BigEndian();
				//reader.ReadBytes(4);
				//reader.ReadBytes(4);
				//reader.ReadBytes(20);
				//var mysterySize = reader.ReadUInt32BigEndian();
				//var mysteryOffset = reader.ReadUInt32BigEndian();

				// mesh data description block
				reader.BaseStream.Position = mddbOffset + 12;
				info.VertexDataBlockSize = reader.ReadUInt32BigEndian();
				info.VertexEntrySize = reader.ReadUInt32BigEndian();
				//reader.ReadBytes(8);
				info.Unk1 = reader.ReadUInt32BigEndian();
				info.Unk2 = reader.ReadUInt32BigEndian();
				info.VertexDataBlockOffset = reader.ReadUInt32BigEndian(); // from start of data block
				//reader.ReadBytes(20);
				info.Unk3 = reader.ReadUInt32BigEndian();
				info.Unk4 = reader.ReadUInt32BigEndian();
				info.Unk5 = reader.ReadUInt32BigEndian();
				info.Unk6 = reader.ReadUInt32BigEndian();
				info.Unk7 = reader.ReadUInt32BigEndian();
				info.StripBlockSize = reader.ReadUInt32BigEndian();
				//reader.ReadBytes(4);
				info.Unk8 = reader.ReadUInt32BigEndian();
				info.StripBlockOffset = reader.ReadUInt32BigEndian();
				info.BoundingSphere = new Sphere(reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian());

				reader.ReadBytes(48);
				info.MaterialSplits = new MaterialSplit[info.MatrialSplitCount];

				var offset = 0;
				for (var j = 0; j < info.MatrialSplitCount; j++)
				{
					var split = new MaterialSplit();

					split.IndexCount = reader.ReadInt32BigEndian();
					//reader.ReadBytes(28);
					//reader.ReadBytes(4);

					split.Unk0 = reader.ReadUInt32BigEndian();
					split.Unk1 = reader.ReadUInt32BigEndian();
					split.Unk2 = reader.ReadUInt32BigEndian();
					split.Unk3 = reader.ReadUInt32BigEndian();
					split.Unk4 = reader.ReadUInt32BigEndian();
					split.Unk5 = reader.ReadUInt32BigEndian();
					split.Unk6 = reader.ReadUInt32BigEndian();
					split.Unk7 = reader.ReadUInt32BigEndian();

					split.IndexOffset = offset;
					offset += split.IndexCount;

					info.MaterialSplits[j] = split;
				}

				var dataBlockStart = 12 + dataBlockOffset;

				var stripBlockStart = dataBlockStart + info.StripBlockOffset;
				var vertexBlockStart = dataBlockStart + info.VertexDataBlockOffset;

				for (var j = 0; j < info.MatrialSplitCount; j++)
				{
					var indicesToTake = info.MaterialSplits[j].IndexCount * 2;

					#region Get strips for this material

					reader.BaseStream.Position = stripBlockStart + (info.MaterialSplits[j].IndexOffset * 2);

					// Indicies are stored as a list of ushorts (uint16)
					var indiceBytes = reader.ReadBytes(indicesToTake);
					var indiceList = new ushort[indiceBytes.Length / 2];
					for (var k = 0; k < indiceBytes.Length; k += 2)
					{
						var byte1 = indiceBytes[k];
						var byte2 = indiceBytes[k + 1];
						indiceList[k / 2] = (ushort)((byte1 << 8) + byte2);
					}

					var stripList = new List<TriStrip>();
					var tempList = new List<int>();
					foreach (var index in indiceList)
					{
						if (index == ushort.MaxValue)
						{
							stripList.Add(new TriStrip
							{
								Indices = tempList.ToArray()
							});
							tempList.Clear();
						}
						else
						{
							tempList.Add(index);
						}
					}

					info.MaterialSplits[j].Strips = stripList.ToArray();

					#endregion

					#region Convert strips into face lists

					var triangleList = new List<int>();

					foreach (var strip in info.MaterialSplits[j].Strips)
					{
						var faces = StripToFaces(strip);
						foreach (var (one, two, three) in faces)
						{
							triangleList.Add(one);
							triangleList.Add(two);
							triangleList.Add(three);
						}
					}

					info.MaterialSplits[j].Triangles = triangleList.ToArray();

					#endregion
				}

				#region Load vertex data

				reader.BaseStream.Position = vertexBlockStart;
				var vertexCount = info.VertexDataBlockSize / info.VertexEntrySize;
				info.Vertices = new Vertex[vertexCount];

				for (var j = 0; j < vertexCount; j++)
				{
					var startingPos = reader.BaseStream.Position;
					var vertex = new Vertex();

					var hasNormal = info.VertexEntrySize >= 28;
					var hasTangent = info.VertexEntrySize == 40;
					var hasTwentyBytes = info.VertexEntrySize >= 48;
					var hasTwoUVSets = info.VertexEntrySize is 36 or 40 or 56;
					var numUVSets = hasTwoUVSets ? 2 : 1;

					Console.WriteLine($"Reading position");
					var x = reader.ReadSingleBigEndian();
					var y = reader.ReadSingleBigEndian();
					var z = reader.ReadSingleBigEndian();
					vertex.Position = new Vector3(x, y, -z);

					if (hasNormal)
					{
						var normalContainer = reader.ReadInt32BigEndian();
						var nZ = (normalContainer & 0xFFC00000) >> 22;
						var nY = (normalContainer & 0x003FF800) >> 11;
						var nX = (normalContainer & 0x000007FF);

						if ((nZ & 512) != 0)
						{
							nZ &= 511;
							nZ -= 512;
						}

						if ((nY & 1024) != 0)
						{
							nY &= 1023;
							nY -= 1024;
						}

						if ((nX & 1024) != 0)
						{
							nX &= 1023;
							nX -= 1024;
						}

						var fnX = nX / 1023f;
						var fnY = nY / 1023f;
						var fnZ = nZ / 511f;

						vertex.Normal = new Vector3(fnX, fnY, -fnZ);
					}

					if (hasTangent)
					{
						var tangentContainer = reader.ReadInt32BigEndian();
						var tZ = (tangentContainer & 0b11111111100000000000000000000000) >> 23;
						var tY = (tangentContainer & 0b00000000011111111111100000000000) >> 11;
						var tX = (tangentContainer & 0b00000000000000000000011111111111);

						if ((tZ & 256) != 0)
						{
							tZ &= 255;
							tZ -= 256;
						}

						if ((tY & 2048) != 0)
						{
							tY &= 2047;
							tY -= 2048;
						}

						if ((tX & 1024) != 0)
						{
							tX &= 1023;
							tX -= 1024;
						}

						vertex.Tangent = new Vector3(tX / 1023f, tY / 2047f, tZ / 255f);
					}

					if (hasTwentyBytes)
					{
						var unknown = reader.ReadBytes(20);
					}

					vertex.RGBA = reader.ReadRwRGBA();

					vertex.TexCoords = new Vector2[numUVSets];

					for (var k = 0; k < numUVSets; k++)
					{
						vertex.TexCoords[k] = new Vector2(reader.ReadSingleBigEndian(), 1 - reader.ReadSingleBigEndian());
					}

					info.Vertices[j] = vertex;
				}

				#endregion

				SubmeshInfos[i] = info;
			}
		}

		public static List<(int one, int two, int three)> StripToFaces(TriStrip strip)
		{
			if (strip == null)
			{
				Debug.LogError("Null TriStrip given to StripToFaces");
			}

			if (strip.Indices == null)
			{
				Debug.LogError("Strip.Indices is null");
			}

			var retList = new List<(int one, int two, int three)>();
			var flipped = true;
			for (var i = 0; i < strip.Indices.Length - 2; i++)
			{
				if (flipped)
				{
					retList.Add((strip.Indices[i + 2], strip.Indices[i + 1], strip.Indices[i]));
				}
				else
				{
					retList.Add((strip.Indices[i + 1], strip.Indices[i + 2], strip.Indices[i]));
				}

				flipped = !flipped;
			}

			return retList;
		}

		[Serializable]
		public class SubmeshHeader
		{
			public uint SubmeshInfoBlockSize;
			public uint SubmeshInfoBlockOffset;
		}

		[Serializable]
		public class SubmeshInfo
		{
			public uint ShaderHash;
			public uint Unk0;
			public uint MatrialSplitCount;

			public uint VertexDataBlockSize;
			public uint VertexEntrySize;
			public uint Unk1;
			public uint Unk2;
			public uint VertexDataBlockOffset;
			public uint Unk3;
			public uint Unk4;
			public uint Unk5;
			public uint Unk6;
			public uint Unk7;
			public uint StripBlockSize;
			public uint Unk8;
			public uint StripBlockOffset;

			public Sphere BoundingSphere;
			public MaterialSplit[] MaterialSplits;
			public Vertex[] Vertices;
		}

		[Serializable]
		public class MaterialSplit
		{
			public int IndexCount;
			public uint Unk0;
			public uint Unk1;
			public uint Unk2;
			public uint Unk3;
			[NonSerialized]
			public uint Unk4;
			public uint Unk5;
			public uint Unk6;
			[NonSerialized]
			public uint Unk7;

			public int IndexOffset;
			public TriStrip[] Strips;
			[NonSerialized]
			public int[] Triangles;
		}

		public class TriStrip
		{
			public int[] Indices;
		}

		public class Vertex
		{
			public Vector3 Position;
			public Vector3 Normal;
			public Vector3 Tangent;
			public Color RGBA;
			public Vector2[] TexCoords;
		}
	}
}