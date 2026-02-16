using Assets.Scripts;
using System;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	internal class TriggerRandom : AttributeHandler
	{
		public string m_targetName;
		public Output[] m_arrOutput = new Output[8];

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			for (var i = 0; i < 8; i++)
			{
				m_arrOutput[i] = new Output();
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
						m_arrOutput[0].fWeight = attr.Data.ToSingleBigEndian();
						break;
					}

					case 2:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_arrOutput[0].target = reader.ReadNullTerminatedString();
						break;
					}

					case 3:
					{
						m_arrOutput[0].fDelay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 4:
					{
						m_arrOutput[1].fWeight = attr.Data.ToSingleBigEndian();
						break;
					}

					case 5:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_arrOutput[1].target = reader.ReadNullTerminatedString();
						break;
					}

					case 6:
					{
						m_arrOutput[1].fDelay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 7:
					{
						m_arrOutput[2].fWeight = attr.Data.ToSingleBigEndian();
						break;
					}

					case 8:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_arrOutput[2].target = reader.ReadNullTerminatedString();
						break;

					}

					case 9:
					{
						m_arrOutput[2].fDelay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 10:
					{
						m_arrOutput[3].fWeight = attr.Data.ToSingleBigEndian();
						break;
					}

					case 11:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_arrOutput[3].target = reader.ReadNullTerminatedString();
						break;
					}

					case 12:
					{
						m_arrOutput[3].fDelay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 13:
					{
						m_arrOutput[4].fWeight = attr.Data.ToSingleBigEndian();
						break;
					}

					case 14:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_arrOutput[4].target = reader.ReadNullTerminatedString();
						break;
					}

					case 15:
					{
						m_arrOutput[4].fDelay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 16:
					{
						m_arrOutput[5].fWeight = attr.Data.ToSingleBigEndian();
						break;
					}

					case 17:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_arrOutput[5].target = reader.ReadNullTerminatedString();
						break;
					}

					case 18:
					{
						m_arrOutput[5].fDelay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 19:
					{
						m_arrOutput[6].fWeight = attr.Data.ToSingleBigEndian();
						break;
					}

					case 20:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_arrOutput[6].target = reader.ReadNullTerminatedString();
						break;
					}

					case 21:
					{
						m_arrOutput[6].fDelay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 22:
					{
						m_arrOutput[7].fWeight = attr.Data.ToSingleBigEndian();
						break;
					}

					case 23:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_arrOutput[7].target = reader.ReadNullTerminatedString();
						break;
					}

					case 24:
					{
						m_arrOutput[7].fDelay = attr.Data.ToSingleBigEndian();
						break;
					}
				}
			}
		}

		[Serializable]
		public class Output
		{
			public float fWeight;
			public string target;
			public float fDelay;
		}
	}
}
