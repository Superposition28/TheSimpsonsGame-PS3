using System;
using System.IO;
using Assets.Scripts;
using UnityEngine;

namespace AttributeHandlers
{
	public class MultiManager : AttributeHandler
	{
		public string m_targetName;
		public uint unk_0;
		public uint unk_1;

		public MultiManagerEvent[] Events = new MultiManagerEvent[8];

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			for (var i = 0; i < 8; i++)
			{
				Events[i] = new MultiManagerEvent();
			}

			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_targetName = reader.ReadNullTerminatedString();
						break;
					}

					case 1:
					{
						unk_0 = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 2:
					{
						unk_1 = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 4:
						Events[0].EventTime = attr.Data.ToSingleBigEndian();
						break;

					case 6:
						Events[1].EventTime = attr.Data.ToSingleBigEndian();
						break;

					case 8:
						Events[2].EventTime = attr.Data.ToSingleBigEndian();
						break;

					case 10:
						Events[3].EventTime = attr.Data.ToSingleBigEndian();
						break;

					case 12:
						Events[4].EventTime = attr.Data.ToSingleBigEndian();
						break;

					case 14:
						Events[5].EventTime = attr.Data.ToSingleBigEndian();
						break;

					case 16:
						Events[6].EventTime = attr.Data.ToSingleBigEndian();
						break;

					case 18:
						Events[7].EventTime = attr.Data.ToSingleBigEndian();
						break;

					case 3:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Events[0].EventName = reader.ReadNullTerminatedString();
						break;
					}

					case 5:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Events[1].EventName = reader.ReadNullTerminatedString();
						break;
					}

					case 7:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Events[2].EventName = reader.ReadNullTerminatedString();
						break;
					}

					case 9:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Events[3].EventName = reader.ReadNullTerminatedString();
						break;
					}

					case 11:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Events[4].EventName = reader.ReadNullTerminatedString();
						break;
					}

					case 13:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Events[5].EventName = reader.ReadNullTerminatedString();
						break;
					}

					case 15:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Events[6].EventName = reader.ReadNullTerminatedString();
						break;
					}

					case 17:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Events[7].EventName = reader.ReadNullTerminatedString();
						break;
					}
				}
			}
		}
	}

	[Serializable]
	public class MultiManagerEvent
	{
		public string EventName;
		public float EventTime;
	}
}