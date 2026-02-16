using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using RWReader;
using RWReader.Sections;
using UnityEngine;

namespace Assets.Scripts.Editor
{
	public static class MeshLoader
	{
		public static List<Mesh> LoadTSGMesh(string filePath)
		{
			if (!_initialized)
			{
				_initialized = true;
				foreach (var item in TSGShaders)
				{
					var hash = SDBM(item);
					HashToShader.Add(hash, item);
					//Debug.Log($"{item} : {hash}");
				}
			}

			var reader = new RWStreamReader();
			var readFile = reader.Read(filePath);

			var earsMeshes = readFile.GetChildren<EARSMesh>();

			var meshList = new List<Mesh>();

			foreach (var eaMesh in earsMeshes)
			{
				var skin = eaMesh.Parent.GetChildren<SkinPLG>().FirstOrDefault();
				var isSkinned = skin != null;

				foreach (var submesh in eaMesh.SubmeshInfos)
				{
					foreach (var split in submesh.MaterialSplits)
					{
						var mesh = new Mesh();

						var verts = submesh.Vertices.Select(x => x.Position).ToList();
						var normals = submesh.Vertices.Select(x => x.Normal).ToList();
						var tangents = submesh.Vertices.Select(x => x.Tangent).ToList();
						var colors = submesh.Vertices.Select(x => x.RGBA).ToList();

						var numTexCoords = submesh.Vertices[0].TexCoords.Length;

						/*for (var i = 0; i < verts.Count; i++)
						{
							var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
							go.transform.position = verts[i];
							go.transform.localScale = Vector3.one / 5f;
							go.name = $"Vertex {i}";
						}*/

						mesh.SetVertices(verts);
						mesh.SetTriangles(split.Triangles, 0);

						for (var i = 0; i < numTexCoords; i++)
						{
							mesh.SetUVs(i, submesh.Vertices.Select(x => x.TexCoords[i]).ToList());
						}
						mesh.SetNormals(normals);
						mesh.SetTangents(tangents.Select(x => new Vector4(x.x, x.y, x.z, 1)).ToList());
						mesh.SetColors(colors);
						mesh.name = $"EAMesh{earsMeshes.IndexOf(eaMesh)}" +
									$"Submesh{Array.IndexOf(eaMesh.SubmeshInfos, submesh)}" +
									$"Material{Array.IndexOf(submesh.MaterialSplits, split)}" +
									$"Shader{HashToShader[submesh.ShaderHash]}";

						/*if (isSkinned)
						{
							mesh.name = "Skinned" + mesh.name;

							var binMesh = eaMesh.GetSibling<BinMeshPLG>().Single();
							var meshData = binMesh.Data[Array.IndexOf(submesh.MaterialSplits, split)];
							var triStrip = meshData.Indices;
							var faces = EARSMesh.StripToFaces(new EARSMesh.TriStrip() { Indices = triStrip });
							var triList = new List<int>();
							foreach (var item in faces)
							{
								triList.Add(item.one);
								triList.Add(item.two);
								triList.Add(item.three);
							}
							//mesh.SetTriangles(triList, 0);

							var boneWeights = new BoneWeight[verts.Count];

							for (var i = 0; i < verts.Count; i++)
							{
								var weight = new BoneWeight();

								var bones = skin.VertexBoneMapping[i];
								var weights = skin.WeightList[i];

								weight.boneIndex0 = bones[0];
								weight.boneIndex1 = bones[1];
								weight.boneIndex2 = bones[2];
								weight.boneIndex3 = bones[3];

								weight.weight0 = weights[0];
								weight.weight1 = weights[1];
								weight.weight2 = weights[2];
								weight.weight3 = weights[3];

								boneWeights[i] = weight;
							}

							mesh.boneWeights = boneWeights;

							mesh.bindposes = skin.SkinToBoneMatrix;
						}*/

						meshList.Add(mesh);
					}
				}
			}

			return meshList;
		}

		private static bool _initialized = false;

		private static List<string> TSGShaders = new List<string>()
		{
			"simpsons_chocolate",
			"simpsons_vfx_rigid_textured",
			"simpsons_rigid_normalmap",
			"simpsons_rigid_multitone",
			"simpsons_projtex",
			"simpsons_rigid_dualtextured_uv",
			"simpsons_skin_dualtextured_uv",
			"simpsons_uv",
			"simpsons_skin_flipbook",
			"simpsons_flipbook",
			"simpsons_sky",
			"simpsons_skin_gloss",
			"simpsons_rigid_gloss",
			"simpsons_rigid_dualtextured",
			"simpsons_skin_dualtextured",
			"simpsons_rigid_textured",
			"simpsons_skin_textured",
			"simpsons_aa_col",
			"simpsons_aa_row",
			"simpsons_edgeAA",
			"simpsons_aa",
			"simpsons_edge",
			"simpsons_rigid",
			"simpsons_skin"
		};

		private static Dictionary<uint, string> HashToShader = new();

		private static uint SDBM(string str)
		{
			str = str.ToLower();

			uint value = 0;
			foreach (var c in str)
			{
				value = (65599 * value) + c;
			}

			return value;
		}
	}
}
