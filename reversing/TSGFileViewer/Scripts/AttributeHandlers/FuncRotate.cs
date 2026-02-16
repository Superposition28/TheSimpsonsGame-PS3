using Assets.Scripts;
using System;
using System.IO;
using System.Linq;
using Assets.Scripts.AttributeHandlers;
using UnityEngine;

namespace AttributeHandlers
{
	public class FuncRotate : AttributeHandler
	{
		public Guid128 UNK_0;
		public Vector3 UNK_1_Axis = new Vector3(1, 0, 0);
		public float UNK_2_Radians;
		public float UNK_3;
		public float UNK_4;
		public uint UNK_5;
		public float UNK_6_Radians;
		public uint UNK_7;
		public string UNK_8;
		public string UNK_9;
		public string UNK_10;
		public string UNK_11;
		public string UNK_12;

		public Transform ObjToRotate;

		private void Start()
		{
			var item = Resources.FindObjectsOfTypeAll<Base>().First(x => x.InstanceID == UNK_0);
			ObjToRotate = item.transform;
		}

		private void FixedUpdate()
		{
			if (ObjToRotate != null)
			{
				ObjToRotate.Rotate(UNK_1_Axis, -UNK_2_Radians * Mathf.Rad2Deg * Time.deltaTime);
			}
		}

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian();
						UNK_0 = new Guid128(reader);
						break;
					}

					case 1:
					{
						var temp = attr.Data.ToUInt32BigEndian();
						UNK_1_Axis = temp switch
						{
							0 => new Vector3(1, 0, 0),
							1 => new Vector3(-1, 0, 0),
							2 => new Vector3(0, 1, 0),
							3 => new Vector3(0, -1, 0),
							4 => new Vector3(0, 0, 1),
							5 => new Vector3(0, 0, -1),
							_ => throw new NotImplementedException()
						};
						break;
					}

					case 2:
					{
						UNK_2_Radians = attr.Data.ToSingleBigEndian() * 0.017453292f;
						break;
					}

					case 3:
					{
						UNK_3 = attr.Data.ToSingleBigEndian();
						break;
					}

					case 4:
					{
						UNK_4 = attr.Data.ToSingleBigEndian();
						break;
					}

					case 5:
					{
						UNK_5 = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 6:
					{
						UNK_6_Radians = attr.Data.ToSingleBigEndian() * 0.017453292f;
						break;
					}

					case 7:
					{
						UNK_7= attr.Data.ToUInt32BigEndian();
						break;
					}

					case 8:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian();
						UNK_8 = reader.ReadNullTerminatedString();
						break;
					}

					case 9:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian();
						UNK_9 = reader.ReadNullTerminatedString();
						break;
					}

					case 10:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian();
						UNK_10 = reader.ReadNullTerminatedString();
						break;
					}

					case 11:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian();
						UNK_11 = reader.ReadNullTerminatedString();
						break;
					}

					case 12:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian();
						UNK_12 = reader.ReadNullTerminatedString();
						break;
					}

					default:
						throw new NotImplementedException();
				}
			}
		}
	}
}