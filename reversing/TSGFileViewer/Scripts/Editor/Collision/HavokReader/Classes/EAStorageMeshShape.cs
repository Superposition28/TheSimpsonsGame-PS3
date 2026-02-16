using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader.Classes
{
	public class EAStorageMeshShape : HavokClass
	{
		public EAStorageMeshShape()
		{
			Name = "EAStorageMeshShape";
		}

		public Vector3[] VertList;
		public int[] FaceList;

		public override Mesh Deserialize(BinaryReader reader)
		{
			reader.ReadBytes(24);

			var vertCount = reader.ReadUInt32BigEndian();
			reader.ReadBytes(8);
			var faceCount = reader.ReadUInt32BigEndian();

			reader.ReadBytes(168);

			var vertList = new List<Vector3>();
			for (var i = 0; i < vertCount; i++)
			{
				var x = reader.ReadSingleBigEndian();
				var y = reader.ReadSingleBigEndian();
				var z = reader.ReadSingleBigEndian();
				vertList.Add(new Vector3(x, y, z));
				reader.ReadBytes(4);
			}

			var indexList = new List<int>();
			while (indexList.Count != faceCount * 3)
			{
				indexList.Add(reader.ReadInt32BigEndian());
			}

			var faceList = new List<int>();

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

			VertList = vertList.ToArray();
			FaceList = faceList.ToArray();

			var mesh = new Mesh();
			mesh.name = $"EAStorageMeshShape";
			mesh.SetVertices(vertList);
			mesh.SetTriangles(faceList, 0);

			return mesh;
		}
	}
}