using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using UnityEditor;
using UnityEditor.Experimental.GraphView;
using UnityEngine;
using UnityEngine.Serialization;

namespace Assets.Scripts
{
	public class NavigationGraph : MonoBehaviour
	{
		public NavigationNode[] Nodes;
		public NavigationConnection[] Connections;

		public TextAsset GraphFile;

		//[InspectorButton(nameof(OnButtonClicked))]
		public bool ExtractData;

		public void OnButtonClicked()
		{
			var bytes = GraphFile.bytes;

			var stream = new MemoryStream(bytes);
			var reader = new BinaryReader(stream);

			reader.ReadInt32BigEndian();
			reader.ReadInt32BigEndian();
			reader.ReadInt32BigEndian(); // version

			var nNodes = reader.ReadInt16BigEndian();
			var nConnections = reader.ReadInt16BigEndian();

			reader.ReadBytes(16); // guid

			var nodeArrayOffset = reader.ReadInt32BigEndian();
			var connectionArrayOffset = reader.ReadInt32BigEndian();

			Nodes = new NavigationNode[nNodes];
			Connections = new NavigationConnection[nConnections];

			reader.BaseStream.Position = nodeArrayOffset;
			for (var i = 0; i < nNodes; i++)
			{
				var node = new NavigationNode();
				node.pos = reader.ReadVector3BigEndian();
				node.pos.z = -node.pos.z;
				node.radius = reader.ReadSingleBigEndian();

				node.iConnection = reader.ReadInt16BigEndian();
				node.propertyInstance = reader.ReadInt16BigEndian();
				node.nConnection = reader.ReadByte();
				node.nNeighborConnection = reader.ReadByte();
				node.iNeighborConnection = reader.ReadInt16BigEndian();
				node.nodeFlags = reader.ReadInt16BigEndian();

				reader.ReadBytes(6);
	
				//reader.ReadBytes(16);

				Nodes[i] = node;
			}

			reader.BaseStream.Position = connectionArrayOffset;
			for (var i = 0; i < nConnections; i++)
			{
				var con = new NavigationConnection();
				con.length = reader.ReadSingleBigEndian();
				con.dstIndex = reader.ReadInt16BigEndian();
				con.srcIndex = reader.ReadInt16BigEndian();
				con.propertyInstance = reader.ReadInt16BigEndian();
				con.connectionFlags = reader.ReadInt16BigEndian();
				con.blockedCount = reader.ReadByte();
				reader.ReadBytes(3); // padding

				Connections[i] = con;
			}
		}

		private void OnDrawGizmosSelected()
		{
			foreach (var node in Nodes)
			{
				if (node.propertyInstance != -1 || node.nodeFlags != 0)
				{
					var text = "";

					if (node.propertyInstance != -1)
					{
						text += $"Prop: {node.propertyInstance}\n";
					}

					if (node.nodeFlags != -1)
					{
						text += $"Flags: {node.nodeFlags}\n";
					}

					Handles.color = Color.yellow;
					Handles.Label(node.pos, text);
				}
				else
				{
					Handles.color = Color.white;
				}

				//Gizmos.DrawWireSphere(node.pos, node.radius);
				Handles.DrawWireDisc(node.pos, Vector3.up, node.radius);
			}

			foreach (var con in Connections)
			{
				var src = Nodes[con.srcIndex];
				var dst = Nodes[con.dstIndex];

				var midpoint = (src.pos + dst.pos) / 2;
				var arrowPos = (midpoint + src.pos) / 2;

				var dir = (dst.pos - src.pos);
				dir.Normalize();
				var normal = Vector3.ProjectOnPlane(Vector3.up, dir).normalized;

				if (con.propertyInstance != -1 || con.connectionFlags != 0)
				{
					Gizmos.color = Color.red;
					var text = "";

					if (con.propertyInstance != -1)
					{
						text += $"Prop: {con.propertyInstance}\n";
					}

					if (con.connectionFlags != 0)
					{
						text += $"Flags:";
						if ((con.connectionFlags & 0x1) != 0)
						{
							// haven't seen this one yet
							Gizmos.color = Color.red;
							text += "???_1, ";
						}

						if ((con.connectionFlags & 0x2) != 0)
						{
							// jumping?
							Gizmos.color = Color.green;
							text += "JUMP, ";
						}

						if ((con.connectionFlags & 0x4) != 0)
						{
							// ladder?
							Gizmos.color = Color.yellow;
							text += "LADDER, ";
						}

						if ((con.connectionFlags & 0x8) != 0)
						{
							// trampoline path?
							Gizmos.color = Color.magenta;
							text += "AIR, ";
						}

						if ((con.connectionFlags & 0x10) != 0)
						{
							// poles?
							Gizmos.color = Color.blue;
							text += "POLE, ";
						}

						if ((con.connectionFlags & 0x20) != 0)
						{
							// ledge hangs?
							Gizmos.color = Color.cyan;
							text += "LEDGE, ";
						}

						if ((con.connectionFlags & 0x40) != 0)
						{
							// grapple hook? surface climbing? idk
							//Gizmos.color = Color.red;
							text += "???_7, ";
						}

						if ((con.connectionFlags & 0x80) != 0)
						{
							// haven't seen this one yet
							Gizmos.color = Color.red;
							text += "???_8, ";
						}
					}

					Handles.Label(arrowPos + normal / 2, text);
				}
				else
				{
					Gizmos.color = Color.white;
				}
				
				Gizmos.DrawLine(src.pos, dst.pos);

				var angle = 30;
				var l = Quaternion.AngleAxis(angle, normal);
				var r = Quaternion.AngleAxis(-angle, normal);

				Gizmos.DrawRay(arrowPos, (l * -dir) / 2);
				Gizmos.DrawRay(arrowPos, (r * -dir) / 2);
			}
		}
	}

	[Serializable]
	public struct NavigationNode
	{
		public Vector3 pos;
		public float radius;
		public short iConnection;
		public short propertyInstance;
		public byte nConnection;
		public byte nNeighborConnection;
		public short iNeighborConnection;
		public short nodeFlags;
	}

	[Serializable]
	public struct NavigationConnection
	{
		public float length;
		public short dstIndex;
		public short srcIndex;
		public short propertyInstance;
		public short connectionFlags;

		public byte blockedCount;
	}
}
