using Assets.Scripts.Resources;
using RWReader;
using RWReader.Sections;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Rendering;
using Material = RWReader.Sections.Material;

namespace Assets.Scripts.ResourceHandlers
{
	public class EARS_MESH : Resource
	{
		public class SplitMesh
		{
			public Mesh UnityMesh;
			public uint Shader;
			public Material Material;
			public int UVCount;
		}

		public Section SectionTree;

		public SplitMesh[] GetMeshes()
		{
			var earsMeshes = SectionTree.GetChildren<EARSMesh>();
			var splitMeshes = new List<SplitMesh>();

			foreach (var earsMesh in earsMeshes)
			{
				var geometry = earsMesh.GetParent<Geometry>();
				var materialList = geometry.GetChild<MaterialList>();
				var materials = materialList.GetMaterials();
				var binMeshPLG = earsMesh.GetSibling<BinMeshPLG>().Single();

				var splitIndex = 0;

				foreach (var submesh in earsMesh.SubmeshInfos)
				{
					foreach (var split in submesh.MaterialSplits)
					{
						var splitMesh = new SplitMesh();

						var positions = submesh.Vertices.Select(x => x.Position).ToList();
						var normals = submesh.Vertices.Select(x => x.Normal).ToList();
						var tangents = submesh.Vertices.Select(x => x.Tangent).ToList();
						var colors = submesh.Vertices.Select(x => x.RGBA).ToList();

						var numTexCoords = submesh.Vertices[0].TexCoords.Length;

						var unityMesh = new Mesh();

						unityMesh.SetVertices(positions);
						unityMesh.SetTriangles(split.Triangles, 0);

						for (var i = 0; i < numTexCoords; i++)
						{
							unityMesh.SetUVs(i, submesh.Vertices.Select(x => x.TexCoords[i]).ToList());
						}

						unityMesh.SetNormals(normals);
						unityMesh.SetTangents(tangents.Select(x => new Vector4(x.x, x.y, x.z, 1)).ToList());
						unityMesh.SetColors(colors);

						unityMesh.name =
							$"Mesh:{earsMeshes.IndexOf(earsMesh)}, " +
							$"Submesh:{Array.IndexOf(earsMesh.SubmeshInfos, submesh)}, " +
							$"Split:{Array.IndexOf(submesh.MaterialSplits, split)}, ";

						splitMesh.UnityMesh = unityMesh;
						splitMesh.Shader = submesh.ShaderHash;

						// TODO: work how materials are actually assigned - both of these are wrong!
						splitMesh.Material = materials[splitIndex++];
						//splitMesh.Material = materials[binMeshPLG.Data[splitIndex++].MaterialIndex];

						splitMesh.UVCount = numTexCoords;

						splitMeshes.Add(splitMesh);
					}
				}
			}

			return splitMeshes.ToArray();
		}
	}

	public class EARS_MESH_Handler : ResourceHandler
	{
		public Dictionary<Guid128, EARS_MESH> Meshes = new();
		public List<Guid128> DebugList = new();
		public List<EARSMesh> DebugList2 = new();

		public override void HandleBytes(byte[] data, Guid128 guid, string strFilePath)
		{
			var section = new RWStreamReader().Read(data);

			var mesh = new EARS_MESH();
			mesh.STRFile = strFilePath;
			mesh.GUID = guid;
			mesh.SectionTree = section;

			foreach (var item in section.GetChildren<EARSMesh>())
			{
				DebugList2.Add(item);
			}

			Meshes.Add(guid, mesh);
			DebugList.Add(guid);
		}

		public override IEnumerable<Resource> GetResources()
		{
			return Meshes.Values;
		}
	}
}