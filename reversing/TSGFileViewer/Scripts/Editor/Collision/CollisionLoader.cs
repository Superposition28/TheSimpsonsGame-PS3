using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace Editor.Collision
{
	public static class CollisionLoader
	{
		private static int classnames_absoluteDataStart;
		private static string hex;
		private static byte[] bytes;
		private static SortedList<int, string> ClassMappings = new SortedList<int, string>();

		public static (List<Mesh>, List<float>) LoadTSGCollider(string filePath)
		{
			Debug.Log($"Loading {filePath}...");
			ClassMappings.Clear();
			var meshList = new List<Mesh>();
			var radiusList = new List<float>();
			bytes = File.ReadAllBytes(filePath);
			hex = BitConverter.ToString(bytes).Replace("-", "");

			var skipTrack = 200;
			classnames_absoluteDataStart = HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray()));
			skipTrack = 296;
			var data_absoluteDataStart = HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray()));
			skipTrack += 8;
			var data_localFixupsOffset = HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray()));
			skipTrack += 8;
			var data_globalFixupsOffset = HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray()));
			skipTrack += 8;
			var data_virtualFixupsOffset = HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray()));

			skipTrack = 32 + (data_absoluteDataStart * 2);
			skipTrack += data_virtualFixupsOffset * 2;
			Debug.Log($"Class Mapping found at {skipTrack / 2} bytes.");

			while (skipTrack != hex.Length && new string(hex.Skip(skipTrack).Take(2).ToArray()) != "FF")
			{
				var offset = HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray()));
				var classOffset = HexToInt(new string(hex.Skip(skipTrack).Skip(16).Take(8).ToArray()));
				var className = GetClassname(classOffset);
				ClassMappings.Add(offset, className);
				skipTrack += 24;
			}

			for (var i = 0; i < ClassMappings.Count; i++)
			{
				var chunkOffset = ClassMappings.Keys[i];
				var classname = ClassMappings.Values[i];
				skipTrack = 32 + (data_absoluteDataStart * 2) + (chunkOffset * 2);

				Debug.Log($"{classname} found at {skipTrack / 2} bytes.");

				switch (classname)
				{
					case "EAStorageMeshShape":
						Debug.Log($"EAStorageMeshShape at {skipTrack / 2}");
						skipTrack += 48;
						var vertCount = HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray()));
						var faceCount = HexToInt(new string(hex.Skip(skipTrack + 24).Take(8).ToArray()));
						skipTrack += 368;
						var vertList = new List<Vector3>();
						for (var v = 0; v < vertCount; v++)
						{
							var xyzHex = new string(hex.Skip(skipTrack).Take(24).ToArray());
							var x = HexToFloat(xyzHex.Substring(0, 8));
							var y = HexToFloat(xyzHex.Substring(8, 8));
							var z = HexToFloat(xyzHex.Substring(16, 8));
							skipTrack += 24;
							vertList.Add(new Vector3(x, y, -z));
							skipTrack += 8;
						}

						var indexList = new List<int>();
						var faceList = new List<int>();
						while (indexList.Count != faceCount * 3)
						{
							indexList.Add(HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray())));
							skipTrack += 8;
						}

						var n = 0;
						while (n < indexList.Count)
						{
							try
							{
								faceList.Add(indexList[n]);
								faceList.Add(indexList[n + 1]);
								faceList.Add(indexList[n + 2]);
							}
							catch
							{
								Debug.LogError("exception when n = " + n + " and indexList count is " + indexList.Count);
								faceList.Add(0);
							}
							n += 3;
						}

						var mesh = new Mesh();
						mesh.name = $"EAStorageMeshShape index {i}";
						mesh.SetVertices(vertList);
						mesh.SetTriangles(faceList, 0);
						//mesh.RecalculateNormals();
						meshList.Add(mesh);
						break;
					case "hkBoxShape":
						skipTrack += 24;
						var convexRadius = HexToFloat(new string(hex.Skip(skipTrack).Take(8).ToArray()));
						var radiusMultiplier = 1 + convexRadius;
						skipTrack += 8;
						var xyzwHalfHex = new string(hex.Skip(skipTrack).Take(32).ToArray());
						var xScale = HexToFloat(xyzwHalfHex.Substring(0, 8)) * radiusMultiplier;
						var yScale = HexToFloat(xyzwHalfHex.Substring(8, 8)) * radiusMultiplier;
						var zScale = HexToFloat(xyzwHalfHex.Substring(16, 8)) * radiusMultiplier;
						var wScale = HexToFloat(xyzwHalfHex.Substring(24, 8)) * radiusMultiplier;

						var (verts, tris, normals, uvs) = CreateCube(xScale, yScale, zScale);

						var cubeMesh = new Mesh();
						cubeMesh.name = $"hkBoxShape index {i}";
						cubeMesh.vertices = verts;
						cubeMesh.triangles = tris;
						cubeMesh.normals = normals;
						cubeMesh.uv = uvs;
						cubeMesh.Optimize();
						meshList.Add(cubeMesh);

						break;
					case "hkSphereShape":
						skipTrack += 24;
						var radius = HexToFloat(new string(hex.Skip(skipTrack).Take(8).ToArray()));
						radiusList.Add(radius);
						break;
					case "hkConvexVerticesShape":
						skipTrack += 24;
						convexRadius = HexToFloat(new string(hex.Skip(skipTrack).Take(8).ToArray()));
						skipTrack += 8;

						var xyzwHalfExtents = new string(hex.Skip(skipTrack).Take(32).ToArray());
						skipTrack += 32;

						var aabbCenter = new string(hex.Skip(skipTrack).Take(32).ToArray());
						skipTrack += 32;
						skipTrack += 8;

						var numberOfFourVectors = HexToInt(new string(hex.Skip(skipTrack).Take(8).ToArray()));
						skipTrack += 16;

						var numberOfVerts = new string(hex.Skip(skipTrack).Take(8).ToArray());
						skipTrack += 16;

						var numberOfPlanes = new string(hex.Skip(skipTrack).Take(8).ToArray());
						skipTrack += 24;

						List<Vector3> originalVectors = new();

						for (var j = 0; j < numberOfFourVectors; j++)
						{
							for (var k = 0; k < 4; k++)
							{
								var vec = new Vector3
								{
									x = HexToFloat(new string(hex.Skip(skipTrack).Take(8).ToArray())),
									y = HexToFloat(new string(hex.Skip(skipTrack + 32).Take(8).ToArray())),
									z = HexToFloat(new string(hex.Skip(skipTrack + 64).Take(8).ToArray()))
								};
								vec *= (1 + convexRadius);
								skipTrack += 8;
								originalVectors.Add(vec);
							}

							skipTrack += (32 * 2);
						}

						var calc = new ConvexHullCalculator();

						var outVerts = new List<Vector3>();
						var outTris = new List<int>();
						var outNormals = new List<Vector3>();

						calc.GenerateHull(originalVectors, true, ref outVerts, ref outTris, ref outNormals);

						var newMesh = new Mesh();
						newMesh.name = $"hkConvexVerticesShape index {i}";
						newMesh.SetVertices(outVerts);
						newMesh.SetTriangles(outTris, 0);
						newMesh.SetNormals(outNormals);
						meshList.Add(newMesh);

						break;
					default:
						Debug.LogWarning($"Unknown classname : {classname}");
						break;
				}
			}
			return (meshList, radiusList);
		}

		private static (Vector3[] verts, int[] tris, Vector3[] normals, Vector2[] uvs) CreateCube(float xScale, float yScale, float zScale)
		{
			//1) Define the co-ordinates of each Corner of the cube 
			Vector3[] c = new Vector3[8];

			c[0] = new Vector3(-xScale, 0, zScale);
			c[1] = new Vector3(xScale, 0, zScale);
			c[2] = new Vector3(xScale, 0, -zScale);
			c[3] = new Vector3(-xScale, 0, -zScale);

			c[4] = new Vector3(-xScale, 2 * yScale, zScale);
			c[5] = new Vector3(xScale, 2 * yScale, zScale);
			c[6] = new Vector3(xScale, 2 * yScale, -zScale);
			c[7] = new Vector3(-xScale, 2 * yScale, -zScale);

			//2) Define the vertices that the cube is composed of:
			Vector3[] vertices = new Vector3[]
			{
				c[0], c[1], c[2], c[3], // Bottom
				c[7], c[4], c[0], c[3], // Left
				c[4], c[5], c[1], c[0], // Front
				c[6], c[7], c[3], c[2], // Back
				c[5], c[6], c[2], c[1], // Right
				c[7], c[6], c[5], c[4]  // Top
			};

			//3) Define each vertex's Normal
			Vector3 up = Vector3.up;
			Vector3 down = Vector3.down;
			Vector3 forward = Vector3.forward;
			Vector3 back = Vector3.back;
			Vector3 left = Vector3.left;
			Vector3 right = Vector3.right;

			Vector3[] normals = new Vector3[]
			{
				down, down, down, down,             // Bottom
				left, left, left, left,             // Left
				forward, forward, forward, forward,	// Front
				back, back, back, back,             // Back
				right, right, right, right,         // Right
				up, up, up, up                      // Top
			};

			//4) Define each vertex's UV co-ordinates
			Vector2 uv00 = new Vector2(0f, 0f);
			Vector2 uv10 = new Vector2(1f, 0f);
			Vector2 uv01 = new Vector2(0f, 1f);
			Vector2 uv11 = new Vector2(1f, 1f);

			Vector2[] uvs = new Vector2[]
			{
				uv11, uv01, uv00, uv10, // Bottom
				uv11, uv01, uv00, uv10, // Left
				uv11, uv01, uv00, uv10, // Front
				uv11, uv01, uv00, uv10, // Back	        
				uv11, uv01, uv00, uv10, // Right 
				uv11, uv01, uv00, uv10  // Top
			};

			//5) Define the Polygons (triangles) that make up the our Mesh (cube)
			int[] triangles = new int[]
			{
				3, 1, 0,        3, 2, 1,        // Bottom	
				7, 5, 4,        7, 6, 5,        // Left
				11, 9, 8,       11, 10, 9,      // Front
				15, 13, 12,     15, 14, 13,     // Back
				19, 17, 16,     19, 18, 17,	    // Right
				23, 21, 20,     23, 22, 21,     // Top
			};

			return (vertices, triangles, normals, uvs);
		}

		private static string GetClassname(int offset)
		{
			var nameStart = (classnames_absoluteDataStart) + (offset) + 16;
			var name = bytes.Skip(nameStart).TakeWhile(x => x.ToString("X2") != "00").ToArray();
			return HexToASCII(BitConverter.ToString(name).Replace("-", ""));
		}

		public static int HexToInt(string hex)
		{
			return int.Parse(hex, System.Globalization.NumberStyles.HexNumber);
		}

		public static float HexToFloat(string hex)
		{
			var intRep = Int32.Parse(hex, System.Globalization.NumberStyles.AllowHexSpecifier);
			return BitConverter.ToSingle(BitConverter.GetBytes(intRep), 0);
		}

		public static string HexToASCII(string hexString)
		{
			var ascii = string.Empty;
			for (var i = 0; i < hexString.Length; i += 2)
			{
				var hs = hexString.Substring(i, 2);
				var decval = Convert.ToUInt32(hs, 16);
				var character = Convert.ToChar(decval);
				ascii += character;
			}
			return ascii;
		}
	}
}
